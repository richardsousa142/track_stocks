"""
Download de demonstrativos CIA aberta (BPA, BPP, DRE, DFC_MI) da CVM.
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
    ANOS_DEMONSTRATIVOS,
    CVM_CIA_ABERTA_ZIP_URL,
    CVM_CONTAS_ATIVO,
    CVM_CONTAS_PASSIVO,
    CVM_CSV_ENCODING,
    CVM_INGEST_SLEEP_DEMO_SEC,
    CVM_PREFIXOS_DFC,
    CVM_PREFIXOS_DRE,
    CVM_REQUEST_TIMEOUT,
    demonstrativos_dir_for,
)

log = logging.getLogger(__name__)


def read_csv_from_zip(url: str, file: str, sep: str = ";") -> pd.DataFrame:
    r = requests.get(url, timeout=CVM_REQUEST_TIMEOUT)
    r.raise_for_status()
    zf = ZipFile(BytesIO(r.content))
    with zf.open(file) as f:
        lines = f.readlines()
    lines = [i.strip().decode(CVM_CSV_ENCODING) for i in lines]
    values = [i.replace("\n", "").strip().split(sep) for i in lines]
    return pd.DataFrame(values[1:], columns=values[0])


def relatorio_cias_abertas(
    ano: int,
    cod: str,
    tipo_periodo: str,
    tipo_demonstrativo: str,
) -> pd.DataFrame:
    tipo_lower = tipo_periodo.lower()
    url = CVM_CIA_ABERTA_ZIP_URL.format(
        tipo_periodo=tipo_periodo,
        tipo_lower=tipo_lower,
        ano=ano,
    )
    arquivo = f"{tipo_lower}_cia_aberta_{cod}_{tipo_demonstrativo}_{ano}.csv"
    return read_csv_from_zip(url, arquivo)


def download_demonstrativos(anos: list[int] | None = None, out_dir: Path | None = None) -> None:
    datas = anos if anos is not None else ANOS_DEMONSTRATIVOS
    target = out_dir if out_dir is not None else demonstrativos_dir_for(None)

    for data in datas:
        log.info("Ano %s", data)
        df_ativo_itr = relatorio_cias_abertas(data, "BPA", "ITR", "con")
        df_ativo_dfp = relatorio_cias_abertas(data, "BPA", "DFP", "con")
        df_passivo_itr = relatorio_cias_abertas(data, "BPP", "ITR", "con")
        df_passivo_dfp = relatorio_cias_abertas(data, "BPP", "DFP", "con")
        df_dre_itr = relatorio_cias_abertas(data, "DRE", "ITR", "con")
        df_dre_dfp = relatorio_cias_abertas(data, "DRE", "DFP", "con")
        df_dfc_mi_itr = relatorio_cias_abertas(data, "DFC_MI", "ITR", "ind")
        df_dfc_mi_dfp = relatorio_cias_abertas(data, "DFC_MI", "DFP", "ind")

        df_ativos = pd.concat([df_ativo_itr, df_ativo_dfp], axis=0)
        df_passivos = pd.concat([df_passivo_itr, df_passivo_dfp], axis=0)
        df_bpa = pd.concat([df_ativos, df_passivos], axis=0)

        df_dre_itr = df_dre_itr.drop(columns=["DT_INI_EXERC"], errors="ignore")
        df_dre_dfp = df_dre_dfp.drop(columns=["DT_INI_EXERC"], errors="ignore")
        df_dre = pd.concat([df_dre_itr, df_dre_dfp], axis=0)

        df_dfc_mi_itr = df_dfc_mi_itr.drop(columns=["DT_INI_EXERC"], errors="ignore")
        df_dfc_mi_dfp = df_dfc_mi_dfp.drop(columns=["DT_INI_EXERC"], errors="ignore")
        df_dfc_mi = pd.concat([df_dfc_mi_itr, df_dfc_mi_dfp], axis=0)

        df_ativos = df_ativos.loc[
            (df_ativos["ORDEM_EXERC"] == "ÚLTIMO")
            & (df_ativos["VL_CONTA"] != "0.0000000000")
            & (df_ativos["DS_CONTA"].isin(CVM_CONTAS_ATIVO))
        ]
        df_passivos = df_passivos.loc[
            (df_passivos["ORDEM_EXERC"] == "ÚLTIMO")
            & (df_passivos["VL_CONTA"] != "0.0000000000")
            & (df_passivos["DS_CONTA"].isin(CVM_CONTAS_PASSIVO))
        ]
        df_bpa = df_bpa.loc[df_bpa["ORDEM_EXERC"] == "ÚLTIMO"]

        df_dre = df_dre.loc[
            (df_dre["ORDEM_EXERC"] == "ÚLTIMO")
            & (df_dre["VL_CONTA"].fillna(0) != 0)
            & (df_dre["CD_CONTA"].str.startswith(CVM_PREFIXOS_DRE, na=False))
        ].drop_duplicates(subset=["CD_CVM", "DT_FIM_EXERC", "CD_CONTA"])

        df_dfc_mi = df_dfc_mi.loc[
            (df_dfc_mi["ORDEM_EXERC"] == "ÚLTIMO")
            & (df_dfc_mi["VL_CONTA"].fillna(0) != 0)
            & (df_dfc_mi["CD_CONTA"].str.startswith(CVM_PREFIXOS_DFC, na=False))
        ].drop_duplicates(subset=["CD_CVM", "DT_FIM_EXERC", "CD_CONTA"])

        year_dir = target / str(data)
        year_dir.mkdir(parents=True, exist_ok=True)
        df_ativos.to_parquet(year_dir / f"df_ativos_{data}.parquet", index=False)
        df_passivos.to_parquet(year_dir / f"df_passivos_{data}.parquet", index=False)
        df_bpa.to_parquet(year_dir / f"df_bpa_{data}.parquet", index=False)
        df_dre.to_parquet(year_dir / f"df_dre_{data}.parquet", index=False)
        df_dfc_mi.to_parquet(year_dir / f"df_dfc_mi_{data}.parquet", index=False)
        time.sleep(CVM_INGEST_SLEEP_DEMO_SEC)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Baixa demonstrativos CVM (ações).")
    p.add_argument("--base-dir", type=str, default=".", help="Raiz do projeto.")
    p.add_argument("--anos", type=int, nargs="*", default=None, help="Anos (default: config).")
    args = p.parse_args()
    base = Path(args.base_dir).resolve()
    out = demonstrativos_dir_for(base)
    download_demonstrativos(anos=args.anos, out_dir=out)
    print(f"Concluído. Saída: {out}")


if __name__ == "__main__":
    main()
