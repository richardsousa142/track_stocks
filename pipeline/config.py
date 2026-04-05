"""
Configuração centralizada — caminhos, URLs, constantes numéricas.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── raiz do projeto / dados ─────────────────────────────────────────────────
BASE_DIR = Path(os.getenv("TRACK_STOCKS_BASE_DIR", ".")).resolve()
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

DEMONSTRATIVOS_DIR = RAW_DIR / "demonstrativos"
FIIS_RAW_DIR = RAW_DIR / "fiis"
DEM_ACOES_DIR = PROCESSED_DIR / "dem_acoes"
INDICADORES_DIR = PROCESSED_DIR / "indicadores"
RESULT_DF_PARQUET = INDICADORES_DIR / "result_df.parquet"
ACOES_INDICADORES_DIR = PROCESSED_DIR / "acoes_indicadores"
FIIS_PROC_DIR = PROCESSED_DIR / "fiis_consolidados"

EMPRESAS_COM_TICKER_CSV = BASE_DIR / "empresas_com_ticker.csv"
CANCELADO_CACHE_PATH = BASE_DIR / "cancelado_cache.json"

# ── PostgreSQL ───────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/track_stocks",
)


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/track_stocks",
    )


# ── mercado / métricas quant ─────────────────────────────────────────────────
TRADING_DAYS = 252
RISK_FREE_ANNUAL = float(os.getenv("RISK_FREE_ANNUAL", "0.1075"))
VAR_CONFIDENCE = 0.95
THRESHOLD = 0.0
BENCHMARK_TICKER = os.getenv("BENCHMARK_TICKER", "^BVSP")
MIN_OBS_FRACTION = 1 / 3
MIN_ROLLING_OBS_FLOOR = 7
QUANT_VALUE_ABS_MAX = 1e17

ROLLING_WINDOWS = {"21d": 21, "63d": 63, "126d": 126, "252d": 252}

# ── anos padrão (ingestion) ──────────────────────────────────────────────────
ANOS_DEMONSTRATIVOS = list(range(2011, 2026))
ANOS_FIIS = list(range(2016, 2026))

# ── ETL fundamentalista / parquets ───────────────────────────────────────────
ARQUIVO_ANUAL = "indicadores_anuais.parquet"
ARQUIVO_TRIMESTRAL = "indicadores_trimestrais.parquet"
NON_INDICATOR_COLS = frozenset({"freq", "empresa", "ano", "trimestre", "dt_fim_exerc"})
BATCH_SIZE = 500

# ── rede / CVM (dem_acoes) ───────────────────────────────────────────────────
CVM_CONNECT_TIMEOUT = 3
CVM_READ_TIMEOUT = 6
CVM_MAX_TENTATIVAS = 2
CVM_RETRY_SLEEP = 0.2
CVM_CHUNK_SIZE = 4096
CVM_USER_AGENT = os.getenv(
    "CVM_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) track-stocks/1.0",
)
CVM_CANCELADO_URL_TEMPLATE = (
    "https://cvmweb.cvm.gov.br/SWB/Sistemas/SCW/CPublica/CiaAb/"
    "ResultBuscaParticCiaAb.aspx?CNPJNome={cnpj_quoted}&TipoConsult=C"
)
SLEEP_APOS_GRAVAR = 0.15
PULAR_NOME_EMPRESA = ("EM LIQUIDAÇÃO", "EM RECUPERAÇÃO JUDICIAL")

# ── CVM HTTP ─────────────────────────────────────────────────────────────────
CVM_REQUEST_TIMEOUT = float(os.getenv("CVM_REQUEST_TIMEOUT", "120"))
CVM_CIA_ABERTA_ZIP_URL = (
    "http://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{tipo_periodo}/DADOS/"
    "{tipo_lower}_cia_aberta_{ano}.zip"
)
CVM_FII_ZIP_URL = (
    "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip"
)
CVM_INGEST_SLEEP_DEMO_SEC = float(os.getenv("CVM_INGEST_SLEEP_DEMO_SEC", "2"))
CVM_INGEST_SLEEP_FII_SEC = float(os.getenv("CVM_INGEST_SLEEP_FII_SEC", "1"))
CVM_CSV_ENCODING = "ISO-8859-1"

CVM_CONTAS_ATIVO = (
    "Ativo total",
    "Ativo Circulante",
    "Ativo Não Circulante",
    "Ativo Realizável a Longo Prazo",
    "Investimentos",
    "Imobilizado",
    "Intangivel",
    "Caixa e Equivalentes de Caixa",
    "Estoques",
    "Aplicações Financeiras",
    "Outros Ativos",
)
CVM_CONTAS_PASSIVO = (
    "Passivo Total",
    "Passivo Circulante",
    "Passivo Não Circulante",
    "Patrimônio Líquido Consolidado",
    "Fornecedores",
)
CVM_PREFIXOS_DRE = (
    "3.01", "3.02", "3.03", "3.04", "3.05",
    "3.06", "3.07", "3.08", "3.09", "3.10", "3.11",
)
CVM_PREFIXOS_DFC = ("6.01", "6.02", "6.03", "6.04", "6.05")

CVM_FII_COLS_GERAL = [
    "CNPJ_Fundo", "Data_Referencia", "Nome_Fundo", "Publico_Alvo",
    "Quantidade_Cotas_Emitidas", "Segmento_Atuacao", "Tipo_Gestao",
    "Nome_Administrador", "CNPJ_Administrador",
]
CVM_FII_COLS_COMPLEMENTO = [
    "CNPJ_Fundo", "Data_Referencia", "Total_Numero_Cotistas",
    "Numero_Cotistas_Pessoa_Fisica", "Numero_Cotistas_Pessoa_Juridica_Nao_Financeira",
    "Valor_Ativo", "Patrimonio_Liquido", "Cotas_Emitidas", "Valor_Patrimonial_Cotas",
    "Percentual_Despesas_Taxa_Administracao", "Percentual_Dividend_Yield_Mes",
]
CVM_FII_RENAME_PRE_2021 = {
    "CNPJ_Fundo": "CNPJ_Fundo_Classe",
    "Nome_Fundo": "Nome_Fundo_Classe",
}

# ── resolução de caminhos com base alternativa (CLI --base-dir) ─────────────


def with_base(root: Path | None) -> Path:
    return root.resolve() if root is not None else BASE_DIR


def data_dir_for(base: Path | None = None) -> Path:
    return with_base(base) / "data"


def raw_dir_for(base: Path | None = None) -> Path:
    return data_dir_for(base) / "raw"


def processed_dir_for(base: Path | None = None) -> Path:
    return data_dir_for(base) / "processed"


def demonstrativos_dir_for(base: Path | None = None) -> Path:
    return raw_dir_for(base) / "demonstrativos"


def dem_acoes_dir_for(base: Path | None = None) -> Path:
    return processed_dir_for(base) / "dem_acoes"


def acoes_indicadores_dir_for(base: Path | None = None) -> Path:
    return processed_dir_for(base) / "acoes_indicadores"


def fiis_raw_dir_for(base: Path | None = None) -> Path:
    return raw_dir_for(base) / "fiis"


def fiis_proc_dir_for(base: Path | None = None) -> Path:
    return processed_dir_for(base) / "fiis_consolidados"


def empresas_ticker_csv_for(base: Path | None = None) -> Path:
    return with_base(base) / "empresas_com_ticker.csv"


def cancelado_cache_path_for(base: Path | None = None) -> Path:
    return with_base(base) / "cancelado_cache.json"


def result_df_parquet_for(base: Path | None = None) -> Path:
    return processed_dir_for(base) / "indicadores" / "result_df.parquet"


def historico_acoes_parquet_for(base: Path | None = None) -> Path:
    return with_base(base) / "historico_acoes.parquet"


def bvsp_parquet_for(base: Path | None = None) -> Path:
    return with_base(base) / "bvsp.parquet"
