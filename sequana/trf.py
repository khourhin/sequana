# -*- coding: utf-8 -*-
#
#  This file is part of Sequana software
#
#  Copyright (c) 2016 - Sequana Development Team
#
#  File author(s):
#      Thomas Cokelaer <thomas.cokelaer@pasteur.fr>
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
import pandas as pd



from sequana.lazy import pylab
from sequana import logger

logger.name = __name__


__all__ = ["TRF"]


class TRF():   # pragma: no cover
    """Tandem Repeat Finder utilities

    The input data is the output of trf tool when using the -d option.
    This is not a CSV file. It contains comments in the middle of the file to
    indicate the name of the contig.

    The output filename has the following filename convention::

        test.fa.2.5.7.80.10.50.2000.dat

    where the numbers indicate the 7 input parameters:

    * Match  = matching weight
    * Mismatch  = mismatching penalty
    * Delta = indel penalty
    * PM = match probability (whole number)
    * PI = indel probability (whole number)
    * Minscore = minimum alignment score to report
    * MaxPeriod = maximum period size to report

    You may use ``-h`` to suppress html output.

    Then, you can use this class to easly identify the pattern you want::

        t = TRF("input.dat")
        query = "length>100 and period_size==3 and entropy>0 and C>20 and A>20 and G>20"
        t.df.query(query)

    """
    def __init__(self, filename):
        self.filename = filename
        self.df = self.scandata()

    def scandata(self):
        """scan output of trf and returns a dataframe

        The format of the output file looks like::

            Tandem Repeats Finder Program 

            some info

            Sequence: chr1

            Parameters: 2 5 7 80 10 50 2000

            10001 10468 6 77.2 6 95 3 801 33 51 0 15 1.43 TAACCC TAACCCTA...
            1 10 6 77.2 6 95 3 801 33 51 0 15 1.43 TAACCC TAACCCTA...

            Sequence: chr2

            Parameters: 2 5 7 80 10 50 2000
    
            10001 10468 6 77.2 6 95 3 801 33 51 0 15 1.43 TAACCC TAACCCTA...

        The dataframe stores a row for each sequence and each pattern found. For
        instance, from the example above you will obtain 3 rows, two for the
        first sequence, and one for the second sequence.
        """
        fin = open(self.filename, "r")
        
        data = []

        sequence_name = None
        # skip lines until we reach "Sequence"
        while sequence_name is None:
            line = fin.readline()
            if line.startswith("Sequence:"):
                sequence_name = line.split()[1].strip()
                logger.info("scanning {}".format(sequence_name))

        # If we concatenate several files, we also want to ignore the header
        for line in fin.readlines():
            if line.startswith('Sequence:'):
                sequence_name = line.split()[1].strip()
                logger.info("scanning {}".format(sequence_name))
            else:
                this_data = line.split()
                if len(this_data) == 15:
                    data.append([sequence_name] + this_data)

        df = pd.DataFrame(data)
        df.columns = ['sequence_name', 'start', 'end', 'period_size', 'CNV',
            'size_consensus', 'percent_matches', 'percent_indels', 'score', 'A', 'C', 'G',
            'T', 'entropy', 'seq1', 'seq2']

        df = df.astype({"start": 'int64', "end": 'int64', "period_size": 'int64'})
        df = df.astype({
            'A': 'float',
            'C': 'float',
            'G': 'float',
            'T': 'float',
            'percent_matches': float,
            'percent_indels': float,
            'size_consensus': float,
            'score': 'float',
            'CNV': 'float',
            'entropy': 'float',
            'period_size': 'float'
            })
        df['length'] = df['end'] - df['start'] + 1


        return df

    def hist_cnvs(self, bins=50, CNVmin=10, motif=['CAG', 'AGC', 'GCA'],
            color="r", log=True):
        """

        histogram of the CNVs related to a given motif.
        As an example, this is triplet CAG. Note that we also add the shifted
        version AGC and GCA.

        """
        self.df.query("CNV>@CNVmin and seq1 in @motif").CNV.hist(bins=bins, log=log,
            color=color)

    def hist_period_size(self, bins=50):
        self.df.period_size.hist(bins=bins)
        pylab.xlabel("repeat length")

    def hist_entropy(self, bins=50):
        self.df.entropy.hist(bins=bins)
        pylab.xlabel("entropy")


    def hist_repet_by_sequence(self):
        # How many repetiations per sequence 
        pylab.hist([len(x) for x in self.df.groupby("sequence_name").groups.values()])
        pylab.xlabel("# repetitions per sequence")

