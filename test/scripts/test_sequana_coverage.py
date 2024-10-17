import os

import pytest
from click.testing import CliRunner

from sequana.scripts import coverage

prog = "sequana_coverage"

from .. import test_dir

bedfile = f"{test_dir}/data/bed/JB409847.bed"
genbank = f"{test_dir}/data/genbank/JB409847.gbk"
fastafile = f"{test_dir}/data/fasta/JB409847.fasta"


def test_run():

    runner = CliRunner()

    results = runner.invoke(coverage.main, ["--help"])
    assert results.exit_code == 0

    results = runner.invoke(coverage.main, ["--version"])
    assert results.exit_code == 0


def test_main(tmpdir):
    directory_run = tmpdir.mkdir("report")
    runner = CliRunner()

    results = runner.invoke(
        coverage.main,
        [
            "-i",
            bedfile,
            "-o",
            "--output-directory",
            str(directory_run),
            "--no-multiqc",
            "--window-median",
            "3001",
            "-r",
            fastafile,
        ],
    )
    assert os.path.exists(str(directory_run / "JB409847/sequana_summary_coverage.json"))
    assert results.exit_code == 0


def __test_main_downloads():
    runner = CliRunner()

    with runner.isolated_filesystem():

        results = runner.invoke(
            coverage.main,
            [
                "--download-reference",
                "JB409847",
            ],
        )
        assert results.exit_code == 0
        assert os.path.exists("JB409847.fa")

        results = runner.invoke(coverage.main, ["--download-genbank", "JB409847"])
        assert results.exit_code == 0
        assert os.path.exists("JB409847.gbk")


def test_multiqc_report_and_annotation(tmpdir):
    directory_run = tmpdir.mkdir("report")
    runner = CliRunner()

    results = runner.invoke(
        coverage.main,
        [
            "-i",
            bedfile,
            "-o",
            "--output-directory",
            str(directory_run),
            "--window-median",
            "3001",
            "--annotation-file",
            genbank,
            "-r",
            fastafile,
            "-H",
            4,
            "-L",
            -4,
        ],
    )
    assert os.path.exists(str(directory_run / "JB409847/sequana_summary_coverage.json"))
    assert os.path.exists(str(directory_run / "multiqc_report.html"))
    assert results.exit_code == 0
