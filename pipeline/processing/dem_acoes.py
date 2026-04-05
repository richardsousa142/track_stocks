"""
Separa demonstrativos brutos por empresa, filtrando canceladas (API CVM).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
from tqdm import tqdm

from pipeline.config import (
    ANOS_DEMONSTRATIVOS,
    CVM_CANCELADO_URL_TEMPLATE,
    CVM_CHUNK_SIZE,
    CVM_CONNECT_TIMEOUT,
    CVM_MAX_TENTATIVAS,
    CVM_READ_TIMEOUT,
    CVM_RETRY_SLEEP,
    CVM_USER_AGENT,
    PULAR_NOME_EMPRESA,
    SLEEP_APOS_GRAVAR,
    cancelado_cache_path_for,
    demonstrativos_dir_for,
    dem_acoes_dir_for,
)

log = logging.getLogger(__name__)

_CANCELADO_CACHE: dict[str, bool] = {}
_CACHE_FILE: Path | None = None


def _carregar_cache(path: Path) -> dict[str, bool]:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _salvar_cache(path: Path, cache: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": CVM_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Connection": "keep-alive",
        }
    )
    return s


def is_cancelado(cnpj: str, session: requests.Session | None = None) -> bool:
    global _CANCELADO_CACHE
    cnpj_s = str(cnpj).strip()
    if not cnpj_s:
        return False
    if cnpj_s in _CANCELADO_CACHE:
        return _CANCELADO_CACHE[cnpj_s]

    sess = session or _session()
    url = CVM_CANCELADO_URL_TEMPLATE.format(cnpj_quoted=quote(cnpj_s, safe=""))
    out = False
    for attempt in range(CVM_MAX_TENTATIVAS):
        try:
            with sess.get(url, timeout=(CVM_CONNECT_TIMEOUT, CVM_READ_TIMEOUT), stream=True) as resp:
                resp.raise_for_status()
                acumulado = b""
                for chunk in resp.iter_content(CVM_CHUNK_SIZE):
                    acumulado += chunk
                    if b"cancelado" in acumulado.lower():
                        out = True
                        break
            break
        except requests.RequestException:
            if attempt == CVM_MAX_TENTATIVAS - 1:
                _CANCELADO_CACHE[cnpj_s] = False
                return False
            time.sleep(CVM_RETRY_SLEEP)

    _CANCELADO_CACHE[cnpj_s] = out
    return out


def _arquivos_demo(base_path: Path, ano: int) -> tuple[Path, Path, Path] | None:
    d = base_path / str(ano)
    if not d.is_dir():
        return None
    files = sorted(os.listdir(d))
    if len(files) < 2:
        return None
    return (
        d / files[1],
        d / files[2],
        d / files[3],
    )


def _empresas_validas(*dfs: pd.DataFrame) -> dict[str, str]:
    unicas = (
        pd.concat([df[["DENOM_CIA", "CNPJ_CIA"]] for df in dfs], ignore_index=True)
        .drop_duplicates("DENOM_CIA")
    )
    mask = ~unicas["DENOM_CIA"].apply(lambda n: any(p in n for p in PULAR_NOME_EMPRESA))
    return dict(zip(unicas.loc[mask, "DENOM_CIA"], unicas.loc[mask, "CNPJ_CIA"]))


def separar_por_empresa(
    raw_dir: Path,
    out_dir: Path,
    anos: list[int] | None = None,
    base_dir: Path | None = None,
) -> None:
    global _CANCELADO_CACHE, _CACHE_FILE
    root = base_dir or raw_dir.parent.parent.parent
    _CACHE_FILE = cancelado_cache_path_for(root)
    _CANCELADO_CACHE = _carregar_cache(_CACHE_FILE)

    datas = anos if anos is not None else ANOS_DEMONSTRATIVOS
    sess = _session()

    empresas_por_ano: dict[int, int] = {}
    for data in tqdm(datas, desc="Mapeando anos", unit="ano"):
        caminhos = _arquivos_demo(raw_dir, data)
        if caminhos is None:
            empresas_por_ano[data] = 0
            continue
        cols = ["DENOM_CIA", "CNPJ_CIA"]
        bpa = pd.read_parquet(caminhos[0], columns=cols)
        dfc = pd.read_parquet(caminhos[1], columns=cols)
        dre = pd.read_parquet(caminhos[2], columns=cols)
        empresas_por_ano[data] = len(_empresas_validas(bpa, dfc, dre))

    total_empresas = sum(empresas_por_ano.values())
    anos_com_dados = sum(1 for n in empresas_por_ano.values() if n > 0)
    ano_idx = 0
    salvos = 0
    out_dir.mkdir(parents=True, exist_ok=True)

    with tqdm(
        total=total_empresas,
        desc="Gravando demonstrativos",
        unit="empresa",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}",
    ) as pbar:
        for data in datas:
            if empresas_por_ano[data] == 0:
                continue
            ano_idx += 1

            caminhos = _arquivos_demo(raw_dir, data)
            if caminhos is None:
                continue
            bpa = pd.read_parquet(caminhos[0])
            dfc = pd.read_parquet(caminhos[1])
            dre = pd.read_parquet(caminhos[2])

            candidatas = _empresas_validas(bpa, dfc, dre)
            validas = {emp for emp, cnpj in candidatas.items() if not is_cancelado(cnpj, sess)}

            demos = [("bpa", bpa), ("dfc", dfc), ("dre", dre)]
            for i, empresa in enumerate(sorted(validas), start=1):
                emp_out = out_dir / empresa
                emp_out.mkdir(parents=True, exist_ok=True)
                for name, df in demos:
                    parte = df.loc[df["DENOM_CIA"] == empresa]
                    if not parte.empty:
                        parte.to_parquet(emp_out / f"{name}_{data}.parquet", index=False)
                        salvos += 1
                        time.sleep(SLEEP_APOS_GRAVAR)

                pbar.update(1)
                pbar.set_postfix(
                    ano=data,
                    ano_prog=f"{ano_idx}/{anos_com_dados}",
                    no_ano=f"{i}/{len(validas)}",
                    arquivos=salvos,
                    refresh=False,
                )

            if _CACHE_FILE is not None:
                _salvar_cache(_CACHE_FILE, _CANCELADO_CACHE)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Separa demonstrativos CVM por empresa.")
    p.add_argument("--base-dir", type=str, default=".", help="Raiz do projeto.")
    p.add_argument("--raw-subdir", type=str, default=None, help="Sobrescreve pasta raw/demonstrativos.")
    args = p.parse_args()
    base = Path(args.base_dir).resolve()
    raw = Path(args.raw_subdir).resolve() if args.raw_subdir else demonstrativos_dir_for(base)
    out = dem_acoes_dir_for(base)
    log.info("raw=%s out=%s", raw, out)
    separar_por_empresa(raw, out, base_dir=base)
    print(f"Concluído. Saída: {out}")


if __name__ == "__main__":
    main()
