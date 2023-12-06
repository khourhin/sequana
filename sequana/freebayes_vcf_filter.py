#
#  This file is part of Sequana software
#
#  Copyright (c) 2016-2021 - Sequana Development Team
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
"""Analysis of VCF file generated by freebayes."""
from collections import defaultdict

import colorlog
import vcfpy

from sequana.lazy import pandas as pd
from sequana.lazy import pylab
from sequana.vcftools import (
    compute_fisher_strand_filter,
    compute_frequency,
    compute_strand_balance,
    strand_ratio,
)

logger = colorlog.getLogger(__name__)


class Variant:
    """Variant reader and dictionary that stores important variant information"""

    def __init__(self, record):
        """.. rubric:: constructor

        :param RecordVariant record: variant record
        :param dict resume: most important informations of variant
        """
        self._record = record
        self._samples = {s.sample: s for s in record.calls}
        self._resume = self._vcf_line_to_dict(record)

    def __str__(self):
        return str(self.record)

    @property
    def record(self):
        return self._record

    @property
    def resume(self):
        return self._resume

    @property
    def samples(self):
        return self._samples

    def _vcf_line_to_dict(self, vcf_line):
        """Convert a VCF line as a dictionnary with the most important
        information to detect real variants.
        """
        # Calcul all important information
        alt_freq = compute_frequency(vcf_line)
        strand_bal = compute_strand_balance(vcf_line)
        fisher = compute_fisher_strand_filter(vcf_line)

        line_dict = {
            "chr": vcf_line.CHROM,
            "position": str(vcf_line.POS),
            "depth": vcf_line.INFO["DP"],
            "reference": vcf_line.REF,
            "alternative": "; ".join(str(x.value) for x in vcf_line.ALT),
            "type": "; ".join(str(x.type) for x in vcf_line.ALT),
            "freebayes_score": vcf_line.QUAL,
            "strand_balance": "; ".join("{0:.3f}".format(x) for x in strand_bal),
            "fisher_pvalue": "; ".join(f"{x}" for x in fisher),
        }
        if len(self.samples) == 1:
            line_dict["frequency"] = "; ".join("{0:.3f}".format(x) for x in alt_freq)
        else:
            for i, s in enumerate(self.record.calls):
                if not s.called:
                    freq = 0
                    info = ".:None:None"
                else:
                    info = f"{s.data['GT']}:{s.data['DP']}:{s.data['GL']}"
                    try:
                        freq = "; ".join("{0:.3f}".format(alt / s.data["DP"]) for alt in s.data["AO"])
                    except TypeError:
                        freq = "{0:.3f}".format(s.data["AO"] / s.data["DP"])
                line_dict[s.sample] = freq
                line_dict["info_{0}".format(i)] = info
        try:
            # If vcf is annotated by snpEff
            annotation = vcf_line.INFO["EFF"][0].split("|")
            effect_type, effect_lvl = annotation[0].split("(")
            try:
                prot_effect, cds_effect = annotation[3].split("/")
            except ValueError:
                cds_effect = annotation[3]
                prot_effect = ""
            ann_dict = {
                "CDS_position": cds_effect[2:],
                "effect_type": effect_type,
                "codon_change": annotation[2],
                "gene_name": annotation[5],
                "mutation_type": annotation[1],
                "prot_effect": prot_effect[2:],
                "prot_size": annotation[4],
                "effect_impact": effect_lvl,
            }
            line_dict = dict(line_dict, **ann_dict)
        except KeyError:
            pass
        return line_dict


class VCF_freebayes:
    """VCF class (Variant Calling Format)

    This class is a wrapping of vcf.Reader class from the pyVCF package. It
    is dedicated for VCF file generated by freebayes. A data frame with all
    variants is produced which can be written as a csv file. It can filter variants
    with a dictionnary of filter parameter. Filter variants are written in a new
    VCF file.

    ::

        from sequana import sequana_data
        from sequana.freebayes_vcf_filter import VCF_freebayes
        vcf_filename = sequana_data("JB409847.vcf")

        # Read the data
        v = VCF_freebayes(vcf_filename)

        # Filter the data
        filter_dict = {"freebayes_score": 200,
                       "frequency": 0.8,
                       "min_depth": 10,
                       "forward_depth":3,
                       "reverse_depth":3,
                       "strand_ratio": 0.2}
        filter_v = v.filter_vcf(filter_dict)
        filter_v.to_vcf('output.filter.vcf')

    Information about strand bias (aka strand balance, or strand ratio). This
    is a type of sequencing bias in which one DNA strand is favored over the other,
    which can result in incorrect evaluation of the amount of evidence observed for
    one allele vs. the other.

    """

    def __init__(self, filename, **kwargs):
        """.. rubric:: constructor

        :param str filename: a vcf file.
        :param kwargs: any arguments accepted by vcf.Reader
        """
        self.filename = filename
        self.rewind()

        # initiate filters dictionary
        self._filters_params = {
            "freebayes_score": 0,
            "frequency": 0,
            "min_depth": 0,
            "forward_depth": 0,
            "reverse_depth": 0,
            "strand_ratio": 0,
        }
        self._is_joint = self._check_if_joint()

    @property
    def filters_params(self):
        """Get or set the filters parameters to select variants of interest.
        Setter take a dictionnary as parameter to update the attribute
        :attr:`VCF_freebayes.filters_params`. Delete will reset different
        variable to 0.

        ::

            v = VCF_freebayes("input.vcf")
            v.filters_params = {"freebayes_score": 200,
                               "frequency": 0.8,
                               "min_depth": 10,
                               "forward_depth":3,
                               "reverse_depth":3,
                               "strand_ratio": 0.2}
        """
        return self._filters_params

    @filters_params.setter
    def filters_params(self, d):
        self._filters_params.update(d)

    @filters_params.deleter
    def filters_params(self):
        self._filters_params = {
            "freebayes_score": 0,
            "frequency": 0,
            "min_depth": 0,
            "forward_depth": 0,
            "reverse_depth": 0,
            "strand_ratio": 0,
        }

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._vcf_reader)

    @property
    def is_joint(self):
        """Get :attr:`VCF_freebayes.is_joint` if the vcf file is a
        joint_freebayes.
        """
        return self._is_joint

    @property
    def samples(self):
        return self._vcf_reader.header.samples.names

    def _check_if_joint(self):
        try:
            if len(self.samples) > 1:
                return True
        except:
            logger.warning("Your input VCF may be empty")
        return False

    def rewind(self):
        """Rewind the reader"""
        self._vcf_reader = vcfpy.Reader.from_path(self.filename)

    def get_variants(self):
        self.rewind()
        return [Variant(v) for v in self]

    def filter_vcf(self, filter_dict=None):
        """Filter variants in the VCF file.

        :param dict filter_dict: dictionary of filters. It updates the
            attribute :attr:`VCF_freebayes.filter_params`

        Return Filtered_freebayes object.
        """
        self.rewind()
        if filter_dict:
            self.filters_params = filter_dict
        variants = [Variant(v) for v in self if self._filter_line(v)]
        return Filtered_freebayes(variants, self)

    def _filter_line(self, vcf_line):
        """Filter variant with parameter set in :attr:`VCF_freebayes.filters`.

        :param vcf.model._Record vcf_line:
        :return: line if all filters are passed.
        """
        if vcf_line.QUAL < self.filters_params["freebayes_score"]:
            return False

        if vcf_line.INFO["DP"] <= self.filters_params["min_depth"]:
            return False

        if self.is_joint:
            return True

        forward_depth = vcf_line.INFO["SRF"] + sum(vcf_line.INFO["SAF"])
        if forward_depth <= self.filters_params["forward_depth"]:
            return False

        reverse_depth = vcf_line.INFO["SRR"] + sum(vcf_line.INFO["SAR"])
        if reverse_depth <= self.filters_params["reverse_depth"]:
            return False

        alt_freq = compute_frequency(vcf_line)
        if alt_freq[0] < self.filters_params["frequency"]:
            return False

        strand_bal = compute_strand_balance(vcf_line)
        if strand_bal[0] < self.filters_params["strand_ratio"]:
            return False

        return True

    def barplot(self):
        """ """
        self.rewind()
        variants = defaultdict(int)

        for item in self:
            variants[Variant(item).resume["type"]] += 1

        keys = sorted(variants.keys())
        pylab.bar(x=list(range(len(keys))), height=[variants[k] for k in keys])
        pylab.xticks(range(len(keys)), keys)

    def manhattan_plot(self, chrom_name, bins=200):
        self.rewind()
        positions = defaultdict(list)
        for item in self:
            v = Variant(item).resume
            if v["chr"] == chrom_name:
                positions[v["type"]].append(v["position"])

        N = len(positions)
        fig, axs = pylab.subplots(nrows=N, ncols=1, sharex="row")
        for i, k in enumerate(positions.keys()):
            axs[i].hist(positions[k], bins=bins)
            axs[i].set_ylabel(k)


class Filtered_freebayes:
    """Variants filtered with VCF_freebayes."""

    def __init__(self, variants, fb_vcf):
        """.. rubric:: constructor

        :param list variants: list of variants record.
        :param VCF_freebayes fb_vcf: class parent.
        """
        self._variants = variants
        self._vcf = fb_vcf
        self._columns = self._create_index()
        self._df = self._vcf_to_df()

    @property
    def variants(self):
        """Get the variant list."""
        return self._variants

    @property
    def df(self):
        """Get the data frame."""
        return self._df

    @property
    def vcf(self):
        """Get the VCF_freebayes object."""
        return self._vcf

    @property
    def columns(self):
        """Get columns index."""
        return self._columns

    def _create_index(self):
        columns = ["chr", "position", "reference", "alternative", "depth"]
        if self.vcf.is_joint:
            columns += self.vcf.samples
        else:
            columns.append("frequency")
        columns += ["strand_balance", "freebayes_score", "fisher_pvalue"]
        try:
            if "effect_type" in self.variants[0].resume.keys():
                columns += [
                    "effect_type",
                    "mutation_type",
                    "effect_impact",
                    "gene_name",
                    "CDS_position",
                    "codon_change",
                    "prot_effect",
                    "prot_size",
                ]
        except IndexError:
            pass
        if self.vcf.is_joint:
            columns += ["info_{0}".format(i) for i in range(len(self.vcf.samples))]
        return columns

    def _vcf_to_df(self):
        """Create a data frame with the most important information contained
        in the VCF file.
        """
        dict_list = [v.resume for v in self.variants]
        df = pd.DataFrame.from_records(dict_list)
        try:
            return df[self.columns]
        except KeyError:
            return df

    def to_csv(self, output_filename, info_field=False):
        """Write DataFrame in CSV format.

        :params str output_filename: output CSV filename.
        """
        with open(output_filename, "w") as fp:
            print("# sequana_variant_calling;{0}".format(self.vcf.filters_params), file=fp)
            if self.df.empty:
                print(",".join(self.columns), file=fp)
            else:
                if info_field:
                    self.df.to_csv(fp, index=False)
                else:
                    self.df.to_csv(fp, index=False, columns=self.columns[: -len(self.vcf.samples)])

    def to_vcf(self, output_filename):
        """Write VCF file in VCF format.

        :params str output_filename: output VCF filename.
        """
        with open(output_filename, "w") as fp:
            vcf_writer = vcfpy.Writer(fp, self._vcf._vcf_reader.header)
            for variant in self.variants:
                vcf_writer.write_record(variant.record)
