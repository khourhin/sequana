#
#  This file is part of Sequana software
#
#  Copyright (c) 2018-2022 - Sequana Development Team
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
import textwrap

import colorlog

from sequana.lazy import pandas as pd
from sequana.lazy import pylab

logger = colorlog.getLogger(__name__)


__all__ = ["BUSCO"]


class BUSCO:
    """Wrapper of the BUSCO output

    "BUSCO provides a quantitative measures for the assessment
    of a genome assembly, gene set, transcriptome completeness, based on
    evolutionarily-informed expectations of gene content from near-universal
    single-copy orthologs selected from OrthoDB v9." -- BUSCO website 2017

    This class reads the full report generated by BUSCO and provides some
    visualisation of this report. The information is stored in a dataframe
    :attr:`df`. The score can be retrieve with the attribute :attr:`score` in
    percentage in the range 0-100.

    :reference: http://busco.ezlab.org/

    .. note:: support version 3.0.1 and new formats from v5.X
    """

    def __init__(self, filename="full_table_test.tsv"):
        """.. rubric:: constructor

        :filename: a valid BUSCO input file (full table). See example in sequana
            code source (testing)

        """
        # version 3.0.1
        try:
            self.df = pd.read_csv(filename, sep="\t", skiprows=4)

            if "Status" not in self.df.columns:  # pragma: no cover
                # version 5.2.2
                self.df = pd.read_csv(filename, sep="\t", skiprows=2)
        except pd.io.parsers.python_parser.ParserError:  # pragma: no cover
            # it may happen that the parsing is incorrect with some files
            self.df = pd.read_csv(filename, sep="\t", skiprows=2)

        self.df.rename({"# Busco id": "ID"}, inplace=True, axis=1)

    def pie_plot(self, filename=None, hold=False):
        """Pie plot of the status (completed / fragment / missed)

        .. plot::
            :include-source:

            from sequana import BUSCO, sequana_data
            b = BUSCO(sequana_data("test_busco_full_table.tsv"))
            b.pie_plot()

        """
        if hold is False:
            pylab.clf()
        self.df.groupby("Status").count()["ID"].plot(kind="pie")
        pylab.ylabel("")
        # pylab.title("Distribution Complete/Fragmented/Missing")
        # pylab.legend()
        if filename:
            pylab.savefig(filename)

    def scatter_plot(self, filename=None, hold=False):
        """Scatter plot of the score versus length of each ortholog

        .. plot::
            :include-source:

            from sequana import BUSCO, sequana_data
            b = BUSCO(sequana_data("test_busco_full_table.tsv"))
            b.scatter_plot()


        Missing are not show since there is no information about contig .
        """
        if hold is False:
            pylab.clf()
        colors = ["green", "orange", "red", "blue"]
        markers = ["o", "s", "x", "o"]
        for i, this in enumerate(["Complete", "Fragmented", "Duplicated"]):
            mask = self.df.Status == this
            if sum(mask) > 0:
                self.df[mask].plot(
                    x="Length",
                    y="Score",
                    kind="scatter",
                    color=colors[i],
                    ax=pylab.gca(),
                    marker=markers[i],
                    label=this,
                )

        pylab.legend()
        pylab.grid()
        if filename:
            pylab.savefig(filename)

    def summary(self):
        """Return summary information of the missing, completed, fragemented
        orthologs

        """
        df = self.df.drop_duplicates(subset=["ID"])
        data = {}
        data["S"] = sum(df.Status == "Complete")
        data["F"] = sum(df.Status == "Fragmented")
        data["D"] = sum(df.Status == "Duplicated")
        data["C"] = data["S"] + data["D"]
        data["M"] = sum(df.Status == "Missing")
        data["total"] = len(df)
        data["C_pc"] = data["C"] * 100.0 / data["total"]
        data["D_pc"] = data["D"] * 100.0 / data["total"]
        data["S_pc"] = data["S"] * 100.0 / data["total"]
        data["M_pc"] = data["M"] * 100.0 / data["total"]
        data["F_pc"] = data["F"] * 100.0 / data["total"]
        return data

    def get_summary_string(self):
        data = self.summary()
        C = data["C_pc"]
        F = data["F_pc"]
        D = data["D_pc"]
        S = data["S_pc"]
        M = data["M_pc"]
        N = data["total"]
        string = "C:{:.1f}%[S:{:.1f}%,D:{:.1f}%],F:{:.1f}%,M:{:.1f}%,n:{}"
        return string.format(C, S, D, F, M, N)

    def _get_score(self):
        return self.summary()["C_pc"]

    score = property(_get_score)

    def __str__(self):
        data = self.summary()
        C = data["C"]
        F = data["F"]
        D = data["D"]
        S = data["S"]
        M = data["M"]
        N = data["total"]
        string = """# BUSCO diagnostic

{}

    {} Complete BUSCOs (C)
    {}   Complete and single-copy BUSCOs (S)
    {}   Complete and duplicated  BUSCOs (D)
    {}   Fragmented BUSCOs (F)
    {}   Missing BUSCOs (M)
    {} Total BUSCO groups searched
    """
        return string.format(self.get_summary_string(), C, S, D, F, M, N)

    def save_core_genomes(self, contig_file, output_fasta_file="core.fasta"):
        """Save the core genome based on busco and assembly output

        The busco file must have been generated from an input contig file.
        In the example below, the busco file was obtained from the **data.contigs.fasta**
        file::

            from sequana import BUSCO
            b = BUSCO("busco_full_table.tsv")
            b.save_core_genomes("data.contigs.fasta", "core.fasta")

        If a gene from the core genome is missing, the extracted gene is made of 100 N's
        If a gene is duplicated, only the best entry (based on the score) is kept.

        If there are 130 genes in the core genomes, the output will
        be a multi-sequence FASTA file made of 130 sequences.

        """
        # local import due to cyclic import
        from sequana import FastA

        f = FastA(contig_file)

        # if we have duplicated hits, we group them and take the best score
        # we then drop the ID to keep the index.
        # Note the fillna set to 0 to include 'Missing' entries
        indices = self.df.fillna(0).groupby("ID")["Score"].nlargest(1).reset_index(level=0, drop=True).index
        subdf = self.df.loc[indices]

        # we sort the entries by gene (core genome) name
        # useful if we want to merge the sequences for a multiple alignment

        with open(output_fasta_file, "w") as fout:
            for record in subdf.to_dict("records"):
                type_ = record["Status"]
                if type_ == "Missing":
                    data = "N" * 100
                    fout.write(f">{ID}\t{type_}:{seqname}:{start}:{end}:{end-start}\n{data}\n")
                else:
                    # get gene/contig information
                    start = int(record["Gene Start"])
                    ID = record["ID"]
                    end = int(record["Gene End"])
                    seqname = record["Sequence"]

                    # save the core gene sequence
                    ctg_index = f.names.index(seqname)
                    data = f.sequences[ctg_index][start:end]
                    data = "\n".join(textwrap.wrap(data, 80))
                    fout.write(f">{ID}\t{type_}:{seqname}:{start}:{end}:{end-start}\n{data}\n")
