"""
pipeline/etl/fiis_indicadores.py
=================================
ETL de indicadores fundamentais de FIIs (sem preço).

Fonte  : data/processed/fiis_consolidados/<fundo>/fii_mensal_consolidado_.parquet
Destino: track_stocks.fato_indicadores  (via empresas + periodos)
         track_stocks.tb_fiis_meta      (metadados do fundo)

Uso:
    python -m pipeline.etl.fiis_indicadores [--full] [--workers N]

Flags:
    --full     Reprocessa fundos que já têm dados (por padrão, pula quem já tem)
    --workers  Paralelismo de I/O (padrão: 4)
"""

from __future__ import annotations

import argparse
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row

from pipeline.config import get_database_url

logger = logging.getLogger(__name__)

# ── Configurações ──────────────────────────────────────────────────────────────

_BASE_DIR = Path("data/processed/fiis_consolidados")
_PARQUET_NAME = "fii_mensal_consolidado_.parquet"

# Colunas numéricas que serão coercidas
_NUM_COLS = [
    "Total_Necessidades_Liquidez", "Disponibilidades", "Titulos_Publicos",
    "Titulos_Privados", "Fundos_Renda_Fixa", "Total_Investido",
    "Direitos_Bens_Imoveis", "Terrenos", "Imoveis_Renda_Acabados",
    "Imoveis_Renda_Construcao", "Imoveis_Venda_Acabados", "Imoveis_Venda_Construcao",
    "Outros_Direitos_Reais", "Acoes", "Debentures", "Bonus_Subscricao",
    "Certificados_Deposito_Valores_Mobiliarios", "Cedulas_Debentures",
    "Fundo_Acoes", "FIP", "FII", "FDIC", "Outras_Cotas_FI",
    "Notas_Promissorias", "Acoes_Sociedades_Atividades_FII",
    "Cotas_Sociedades_Atividades_FII", "CEPAC",
    "CRI", "CRI_CRA", "Letras_Hipotecarias", "LCI", "LCI_LCA", "LIG",
    "Outros_Valores_Mobliarios", "Valores_Receber", "Contas_Receber_Aluguel",
    "Contas_Receber_Venda_Imoveis", "Outros_Valores_Receber",
    "Rendimentos_Distribuir", "Taxa_Administracao_Pagar", "Taxa_Performance_Pagar",
    "Obrigacoes_Aquisicao_Imoveis", "Adiantamento_Venda_Imoveis",
    "Adiantamento_Alugueis", "Obrigacoes_Securitizacao_Recebiveis",
    "Instrumentos_Financeiros_Derivativos", "Provisoes_Contigencias",
    "Outros_Valores_Pagar", "Total_Passivo",
    "Total_Numero_Cotistas", "Numero_Cotistas_Pessoa_Fisica",
    "Numero_Cotistas_Pessoa_Juridica_Nao_Financeira",
    "Valor_Ativo", "Patrimonio_Liquido",
    "Cotas_Emitidas", "Quantidade_Cotas_Emitidas", "Valor_Patrimonial_Cotas",
    "Percentual_Despesas_Taxa_Administracao", "Percentual_Dividend_Yield_Mes",
]


# ── Utilitários ────────────────────────────────────────────────────────────────

def _norm_cnpj(raw: str) -> str:
    return re.sub(r"\D", "", str(raw))[:14].zfill(14)


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    if math.isnan(a) or math.isnan(b) or b == 0:
        return None
    return a / b


def _n(row: pd.Series, col: str) -> float | None:
    v = row.get(col)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


# ── Descoberta de arquivos ─────────────────────────────────────────────────────

def discover_parquets(base: Path = _BASE_DIR) -> Iterator[Path]:
    """Percorre a hierarquia de pastas e retorna todos os parquets FII.

    Suporta até 2 níveis de aninhamento:
        base/<fundo>/fii_mensal_consolidado_.parquet
        base/<fundo>/<subpasta>/fii_mensal_consolidado_.parquet
    """
    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        for parquet in folder.rglob(_PARQUET_NAME):
            yield parquet
            break  # um arquivo por fundo


# ── Leitura e limpeza ──────────────────────────────────────────────────────────

def load_and_clean(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        logger.warning("Falha ao ler %s: %s", path, exc)
        return None

    if df.empty:
        return None

    # Coerce numérico — todas as colunas vêm como object
    for col in _NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normaliza data de referência
    df["Data_Referencia"] = pd.to_datetime(df["Data_Referencia"], errors="coerce")
    df = df.dropna(subset=["Data_Referencia", "CNPJ_Fundo_Classe"])

    # Remove duplicatas: mantém versão mais recente por CNPJ + data
    if "Versao" in df.columns:
        df["Versao"] = pd.to_numeric(df["Versao"], errors="coerce").fillna(1)
        df = (
            df.sort_values("Versao", ascending=False)
            .drop_duplicates(subset=["CNPJ_Fundo_Classe", "Data_Referencia"])
        )
    else:
        df = df.drop_duplicates(subset=["CNPJ_Fundo_Classe", "Data_Referencia"])

    df = df.sort_values("Data_Referencia").reset_index(drop=True)
    return df


# ── Cálculo de indicadores ─────────────────────────────────────────────────────

def _compute_indicators(row: pd.Series) -> dict[str, float | None]:
    """Calcula todos os indicadores FII a partir de uma linha do DataFrame."""

    ativo     = _n(row, "Valor_Ativo")
    pl        = _n(row, "Patrimonio_Liquido")
    passivo   = _n(row, "Total_Passivo")
    dispon    = _n(row, "Disponibilidades")
    investido = _n(row, "Total_Investido")
    liquidez  = _n(row, "Total_Necessidades_Liquidez")

    # Sub-itens de carteira
    tit_pub  = _n(row, "Titulos_Publicos")
    tit_priv = _n(row, "Titulos_Privados")
    frf      = _n(row, "Fundos_Renda_Fixa")
    imoveis  = _n(row, "Direitos_Bens_Imoveis")
    imov_r   = _n(row, "Imoveis_Renda_Acabados")
    imov_c   = _n(row, "Imoveis_Renda_Construcao")
    terrenos = _n(row, "Terrenos")
    cri      = _n(row, "CRI")  or 0.0
    cri_cra  = _n(row, "CRI_CRA") or 0.0
    lci      = _n(row, "LCI") or 0.0
    lci_lca  = _n(row, "LCI_LCA") or 0.0
    lig      = _n(row, "LIG") or 0.0
    out_mob  = _n(row, "Outros_Valores_Mobliarios")
    dir_reais = _n(row, "Outros_Direitos_Reais")
    receber  = _n(row, "Valores_Receber")
    aluguel  = _n(row, "Contas_Receber_Aluguel")
    acoes    = _n(row, "Acoes")
    fii_cotas = _n(row, "FII")

    # Taxas
    taxa_adm  = _n(row, "Taxa_Administracao_Pagar")
    taxa_perf = _n(row, "Taxa_Performance_Pagar")
    pct_adm   = _n(row, "Percentual_Despesas_Taxa_Administracao")

    # Cotistas
    total_cot = _n(row, "Total_Numero_Cotistas")
    cot_pf    = _n(row, "Numero_Cotistas_Pessoa_Fisica")
    cot_pj    = _n(row, "Numero_Cotistas_Pessoa_Juridica_Nao_Financeira")

    # Rendimentos / DY
    rendim  = _n(row, "Rendimentos_Distribuir")
    dy_mes  = _n(row, "Percentual_Dividend_Yield_Mes")

    vpc     = _n(row, "Valor_Patrimonial_Cotas")
    cotas   = _n(row, "Quantidade_Cotas_Emitidas") or _n(row, "Cotas_Emitidas")

    def pct_ativo(v: float | None) -> float | None:
        return _safe_div(v, ativo)

    caixa_total = (dispon or 0) + (tit_pub or 0) + (frf or 0)

    return {
        # Patrimonial
        "fii_vpc":                            vpc,
        "fii_patrimonio_liquido":             pl,
        "fii_total_ativo":                    ativo,
        "fii_total_passivo":                  passivo,
        "fii_passivo_sobre_ativo":            _safe_div(passivo, ativo),
        "fii_passivo_sobre_pl":               _safe_div(passivo, pl),
        "fii_disponibilidades_sobre_ativo":   _safe_div(dispon, ativo),
        "fii_disponibilidades_sobre_passivo": _safe_div(dispon, passivo),

        # Composição
        "fii_pct_total_investido":          pct_ativo(investido),
        "fii_pct_liquidez":                 pct_ativo(liquidez),
        "fii_pct_caixa":                    pct_ativo(caixa_total),
        "fii_pct_titulos_publicos":         pct_ativo(tit_pub),
        "fii_pct_titulos_privados":         pct_ativo(tit_priv),
        "fii_pct_fundos_renda_fixa":        pct_ativo(frf),
        "fii_pct_imoveis":                  pct_ativo(imoveis),
        "fii_pct_imoveis_renda_acabados":   pct_ativo(imov_r),
        "fii_pct_imoveis_construcao":       pct_ativo(imov_c),
        "fii_pct_terrenos":                 pct_ativo(terrenos),
        "fii_pct_cri_cra":                  pct_ativo(cri + cri_cra),
        "fii_pct_lci_lca_lig":              pct_ativo(lci + lci_lca + lig),
        "fii_pct_outros_mob":               pct_ativo(out_mob),
        "fii_pct_direitos_reais":           pct_ativo(dir_reais),
        "fii_pct_recebiveis":               pct_ativo((receber or 0) + (aluguel or 0)),
        "fii_pct_fii_cotas":                pct_ativo(fii_cotas),
        "fii_pct_acoes":                    pct_ativo(acoes),

        # Taxas
        "fii_pct_despesas_adm":             pct_adm,
        "fii_taxa_adm_pagar_sobre_pl":      _safe_div(taxa_adm, pl),
        "fii_taxa_perf_pagar_sobre_pl":     _safe_div(taxa_perf, pl),

        # Proventos
        "fii_dy_mes":                       dy_mes,
        "fii_rendimentos_sobre_pl":         _safe_div(rendim, pl),

        # Cotistas
        "fii_total_cotistas":               total_cot,
        "fii_pct_cotistas_pf":              _safe_div(cot_pf, total_cot),
        "fii_pct_cotistas_pj_nao_fin":      _safe_div(cot_pj, total_cot),
        "fii_cotas_emitidas":               cotas,
    }


# ── Persistência ───────────────────────────────────────────────────────────────

_SQL_UPSERT_EMPRESA = """
INSERT INTO track_stocks.empresas
    (razao_social, cnpj_original, cnpj_normalizado)
VALUES (%s, %s, %s)
ON CONFLICT (cnpj_normalizado) DO UPDATE
    SET razao_social  = EXCLUDED.razao_social,
        atualizado_em = now()
RETURNING empresa_id;
"""

_SQL_GET_EMPRESA = """
SELECT empresa_id FROM track_stocks.empresas
WHERE cnpj_normalizado = %s;
"""

_SQL_UPSERT_META = """
INSERT INTO track_stocks.tb_fiis_meta
    (empresa_id, cnpj_fundo, nome_fundo, segmento_atuacao, tipo_gestao,
     publico_alvo, nome_administrador, cnpj_administrador, atualizado_em)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
ON CONFLICT (empresa_id) DO UPDATE
    SET nome_fundo         = EXCLUDED.nome_fundo,
        segmento_atuacao   = EXCLUDED.segmento_atuacao,
        tipo_gestao        = EXCLUDED.tipo_gestao,
        publico_alvo       = EXCLUDED.publico_alvo,
        nome_administrador = EXCLUDED.nome_administrador,
        cnpj_administrador = EXCLUDED.cnpj_administrador,
        atualizado_em      = now();
"""

_SQL_INSERT_PERIODO = """
INSERT INTO track_stocks.periodos (freq, ano, mes, dt_referencia)
VALUES ('M', %s, %s, %s)
ON CONFLICT DO NOTHING;
"""

_SQL_GET_PERIODO = """
SELECT periodo_id FROM track_stocks.periodos
WHERE freq = 'M' AND ano = %s AND mes = %s;
"""

_SQL_GET_INDICADOR = """
SELECT indicador_id FROM track_stocks.indicadores WHERE codigo = %s;
"""

_SQL_UPSERT_FATO = """
INSERT INTO track_stocks.fato_indicadores
    (empresa_id, periodo_id, indicador_id, valor, calculado_em)
VALUES (%s, %s, %s, %s, now())
ON CONFLICT (empresa_id, periodo_id, indicador_id) DO UPDATE
    SET valor        = EXCLUDED.valor,
        calculado_em = now();
"""

_SQL_DONE_CNPJS = """
SELECT DISTINCT e.cnpj_normalizado
FROM track_stocks.tb_fiis_meta m
JOIN track_stocks.empresas e ON e.empresa_id = m.empresa_id
JOIN track_stocks.fato_indicadores f ON f.empresa_id = e.empresa_id
JOIN track_stocks.indicadores i ON i.indicador_id = f.indicador_id
WHERE i.bloco = 'FII';
"""


def _get_or_create_empresa(cur: psycopg.Cursor, cnpj_norm: str, nome: str) -> int:
    cur.execute(_SQL_GET_EMPRESA, (cnpj_norm,))
    row = cur.fetchone()
    if row:
        return row["empresa_id"]
    cur.execute(_SQL_UPSERT_EMPRESA, (nome, cnpj_norm, cnpj_norm))
    row = cur.fetchone()
    return row["empresa_id"]


def _get_or_create_periodo(cur: psycopg.Cursor, dt: pd.Timestamp) -> int:
    cur.execute(_SQL_GET_PERIODO, (dt.year, dt.month))
    row = cur.fetchone()
    if row:
        return row["periodo_id"]
    cur.execute("SAVEPOINT sp_periodo")
    try:
        cur.execute(_SQL_INSERT_PERIODO, (dt.year, dt.month, dt.date()))
        cur.execute("RELEASE SAVEPOINT sp_periodo")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT sp_periodo")
    cur.execute(_SQL_GET_PERIODO, (dt.year, dt.month))
    return cur.fetchone()["periodo_id"]


def _load_indicator_map(cur: psycopg.Cursor) -> dict[str, int]:
    cur.execute("SELECT codigo, indicador_id FROM track_stocks.indicadores WHERE bloco = 'FII'")
    return {r["codigo"]: r["indicador_id"] for r in cur.fetchall()}


def persist_fundo(
    df: pd.DataFrame,
    dsn: str,
    indicator_map: dict[str, int],
) -> tuple[str, int]:
    """Persiste um fundo inteiro (todas as datas). Retorna (cnpj, n_rows)."""

    # Extrai metadados da última linha (mais recente)
    last = df.iloc[-1]
    cnpj_raw  = str(last["CNPJ_Fundo_Classe"])
    cnpj_norm = _norm_cnpj(cnpj_raw)
    nome      = str(last.get("Nome_Fundo_Classe", cnpj_norm) or cnpj_norm)
    segmento  = str(last.get("Segmento_Atuacao", "") or "")
    tipo_gest = str(last.get("Tipo_Gestao", "") or "")
    pub_alvo  = str(last.get("Publico_Alvo", "") or "")
    nome_adm  = str(last.get("Nome_Administrador", "") or "")
    cnpj_adm_raw = str(last.get("CNPJ_Administrador", "") or "")
    cnpj_adm  = _norm_cnpj(cnpj_adm_raw) if cnpj_adm_raw.strip() else None

    n_rows = 0

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            empresa_id = _get_or_create_empresa(cur, cnpj_norm, nome)

            cur.execute(_SQL_UPSERT_META, (
                empresa_id, cnpj_norm, nome, segmento, tipo_gest,
                pub_alvo, nome_adm, cnpj_adm,
            ))

            batch: list[tuple] = []
            for _, row in df.iterrows():
                dt = row["Data_Referencia"]
                periodo_id = _get_or_create_periodo(cur, dt)
                indicadores = _compute_indicators(row)

                for codigo, valor in indicadores.items():
                    if valor is None or (isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor))):
                        continue
                    ind_id = indicator_map.get(codigo)
                    if ind_id is None:
                        continue
                    batch.append((empresa_id, periodo_id, ind_id, valor))

            if batch:
                cur.executemany(_SQL_UPSERT_FATO, batch)
                n_rows = len(batch)

        conn.commit()

    return cnpj_norm, n_rows


# ── Ponto de entrada ───────────────────────────────────────────────────────────

def run(full: bool = False, workers: int = 4) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    dsn = get_database_url()

    # Sincroniza schema + catálogo
    from sql.schema import create_schema_and_catalog
    create_schema_and_catalog()

    # FIIs já processados (pula se --full não foi passado)
    done_cnpjs: set[str] = set()
    if not full:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(_SQL_DONE_CNPJS)
                done_cnpjs = {r["cnpj_normalizado"] for r in cur.fetchall()}
        logger.info("Fundos já processados: %d (use --full para reprocessar)", len(done_cnpjs))

    # Mapa de indicadores (carrega uma vez)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            indicator_map = _load_indicator_map(cur)

    if not indicator_map:
        logger.error("Nenhum indicador FII encontrado no catálogo. Rode create_schema_and_catalog primeiro.")
        return

    logger.info("Indicadores FII no catálogo: %d", len(indicator_map))

    # Descobre arquivos
    parquets = list(discover_parquets())
    logger.info("Arquivos parquet encontrados: %d", len(parquets))

    # Filtra já processados
    tasks: list[pd.DataFrame] = []
    skipped = 0
    for p in parquets:
        df = load_and_clean(p)
        if df is None or df.empty:
            continue
        cnpj_norm = _norm_cnpj(str(df.iloc[-1]["CNPJ_Fundo_Classe"]))
        if cnpj_norm in done_cnpjs:
            skipped += 1
            continue
        tasks.append(df)

    logger.info(
        "Fundos a processar: %d  |  ignorados (já feitos): %d",
        len(tasks), skipped,
    )

    total_rows = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(persist_fundo, df, dsn, indicator_map): df
            for df in tasks
        }
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                cnpj, n = fut.result()
                total_rows += n
                if i % 100 == 0 or i == len(tasks):
                    logger.info("Progresso: %d/%d fundos | %d registros inseridos", i, len(tasks), total_rows)
            except Exception as exc:
                errors += 1
                logger.error("Erro em fundo: %s", exc)

    logger.info(
        "ETL FII concluído: %d fundos | %d registros | %d erros",
        len(tasks) - errors, total_rows, errors,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL de indicadores FII")
    parser.add_argument("--full", action="store_true", help="Reprocessa todos os fundos")
    parser.add_argument("--workers", type=int, default=4, help="Threads de persistência")
    args = parser.parse_args()
    run(full=args.full, workers=args.workers)
