"""
Download e consolidação de dados mensais de FIIs (CVM).
"""

from __future__ import annotations

import argparse
import logging
import time
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import requests

from pipeline.config import (
    ANOS_FIIS,
    CVM_FII_COLS_COMPLEMENTO,
    CVM_FII_COLS_GERAL,
    CVM_FII_RENAME_PRE_2021,
    CVM_FII_ZIP_URL,
    CVM_CSV_ENCODING,
    CVM_INGEST_SLEEP_FII_SEC,
    CVM_REQUEST_TIMEOUT,
    fiis_proc_dir_for,
    fiis_raw_dir_for,
)

log = logging.getLogger(__name__)


def get_fii_csv_from_cvm(url: str, file: str, sep: str = ";") -> pd.DataFrame:
    r = requests.get(url, timeout=CVM_REQUEST_TIMEOUT)
    r.raise_for_status()
    zf = ZipFile(BytesIO(r.content))
    with zf.open(file) as f:
        lines = f.readlines()
    lines = [i.strip().decode(CVM_CSV_ENCODING) for i in lines]
    values = [i.replace("\n", "").strip().split(sep) for i in lines]
    return pd.DataFrame(values[1:], columns=values[0])


def download_fiis(anos: list[int] | None = None, out_dir: Path | None = None) -> None:
    datas = anos if anos is not None else ANOS_FIIS
    target = out_dir if out_dir is not None else fiis_raw_dir_for(None)

    cols1 = list(CVM_FII_COLS_GERAL)
    cols2 = list(CVM_FII_COLS_COMPLEMENTO)

    for data in datas:
        log.info("FII ano %s", data)
        url = CVM_FII_ZIP_URL.format(ano=data)
        arquivo_1 = f"inf_mensal_fii_geral_{data}.csv"
        arquivo_2 = f"inf_mensal_fii_complemento_{data}.csv"
        arquivo_3 = f"inf_mensal_fii_ativo_passivo_{data}.csv"
        df_1 = get_fii_csv_from_cvm(url, arquivo_1)
        df_2 = get_fii_csv_from_cvm(url, arquivo_2)
        df_3 = get_fii_csv_from_cvm(url, arquivo_3)

        year_dir = target / str(data)
        year_dir.mkdir(parents=True, exist_ok=True)
        c1 = list(cols1)
        c2 = list(cols2)
        if data >= 2021:
            c1[0] = "CNPJ_Fundo_Classe"
            c1[2] = "Nome_Fundo_Classe"
            c2[0] = "CNPJ_Fundo_Classe"

        df_1[c1].to_parquet(year_dir / f"fii_mensal_geral_{data}.parquet")
        df_2[c2].to_parquet(year_dir / f"fii_mensal_complemento_{data}.parquet")
        df_3.to_parquet(year_dir / f"fii_mensal_ativo_passivo_{data}.parquet")
        time.sleep(CVM_INGEST_SLEEP_FII_SEC)


def consolidar_fiis(raw_dir: Path | None = None, out_dir: Path | None = None) -> None:
    raw = raw_dir if raw_dir is not None else fiis_raw_dir_for(None)
    out = out_dir if out_dir is not None else fiis_proc_dir_for(None)

    years = sorted(int(p.name) for p in raw.iterdir() if p.is_dir() and p.name.isdigit())
    if not years:
        log.warning("Nenhuma pasta de ano em %s", raw)
        return

    ref_year = max(years)
    geral_ref = raw / str(ref_year) / f"fii_mensal_geral_{ref_year}.parquet"
    df_base = pd.read_parquet(geral_ref)
    cnpj_col = "CNPJ_Fundo_Classe"

    all_data = []
    for yr in years:
        d = raw / str(yr)
        files = sorted(p.name for p in d.iterdir() if p.suffix == ".parquet")
        if len(files) < 3:
            log.warning("Pulando %s: parquets insuficientes", yr)
            continue
        df_ap = pd.read_parquet(d / files[0])
        df_comp = pd.read_parquet(d / files[1])
        df_geral = pd.read_parquet(d / files[2])

        if yr < 2021:
            df_ap = df_ap.rename(columns=CVM_FII_RENAME_PRE_2021)
            df_comp = df_comp.rename(columns=CVM_FII_RENAME_PRE_2021)
            df_geral = df_geral.rename(columns=CVM_FII_RENAME_PRE_2021)

        df_merge = (
            df_ap.merge(df_comp, on=[cnpj_col, "Data_Referencia"], how="left")
            .merge(df_geral, on=[cnpj_col, "Data_Referencia"], how="left")
        )
        all_data.append(df_merge)

    if not all_data:
        return

    df_all = pd.concat(all_data).sort_values("Data_Referencia")
    cnpj_validos = df_base[cnpj_col].unique().tolist()
    df_all = df_all[df_all[cnpj_col].isin(cnpj_validos)]

    for _, df_cnpj in df_all.groupby(cnpj_col):
        nome_fundo = df_cnpj["Nome_Fundo_Classe"].iloc[0]
        fundo_dir = out / str(nome_fundo)
        fundo_dir.mkdir(parents=True, exist_ok=True)
        df_cnpj.to_parquet(fundo_dir / "fii_mensal_consolidado_.parquet")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="FII CVM: download e/ou consolidação.")
    p.add_argument("--base-dir", type=str, default=".")
    p.add_argument("--anos", type=int, nargs="*", default=None)
    p.add_argument("--only-consolidate", action="store_true")
    args = p.parse_args()
    base = Path(args.base_dir).resolve()
    raw = fiis_raw_dir_for(base)
    proc = fiis_proc_dir_for(base)
    if args.only_consolidate:
        consolidar_fiis(raw, proc)
        print(f"Consolidado em: {proc}")
    else:
        download_fiis(anos=args.anos, out_dir=raw)
        print(f"Download em: {raw}")


if __name__ == "__main__":
    main()
