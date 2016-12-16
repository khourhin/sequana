import os
import shutil
import glob
import sys
from optparse import OptionParser
import argparse

import pandas as pd


class Options(argparse.ArgumentParser):
    def  __init__(self, prog="sequana_summary"):
        usage = """Welcome to SEQUANA - Summary standalone

            sequana_summary --file file.fastq.gz
            sequana_summary --glob "file*.fastq"
            sequana_summary --glob "file*.bed"

AUTHORS: Thomas Cokelaer, Dimitri Desvillechabrol
Documentation: http://sequana.readthedocs.io
Issues: http://github.com/sequana/sequana
        """
        description = """DESCRIPTION:

        prints basic stats about a set of input files.

        THe format of the input files must be homogeneous with one of the
        following extensions:

            - fastq or fastq.gz
            - bed (coverage BED files)
        """

        super(Options, self).__init__(usage=usage, prog=prog,
                description=description)

        # options to fill the config file
        self.add_argument("-m", "--multiple", action="store_true", default=False)
        self.add_argument("-q", "--quiet", action="store_true", default=False)

        self.add_argument("-f", "--file", dest="file", type=str,
            required=False, help="""one filename (either FastQ or BED file; see
                DESCRIPTION)""")
        self.add_argument("-g", "--glob", dest="glob", type=str,
            required=False, help="""a glob/pattern of files. Must use quotes
                e.g. "*.fastq.gz" (See --file or DESCRIPTION for details)""")
        self.add_argument("-n", "--sample", default=1000000000000000, type=int,
            help="""If input FastQ files, analyse entire file. You may restrict
                analysis to set of reads""")
        self.add_argument("-t", "--thread", default=4, type=int, 
            help="""Several files may be processed in parallel. By default 4
                threads are used""")

def get_fastq_stats(filename, sample=1e16):
    from sequana import FastQC
    ff = FastQC(filename, max_sample=sample, verbose=False)
    stats = ff.get_stats()
    return stats

def get_bed_stats(filename):
    from sequana import GenomeCov
    import pandas as pd
    bed = GenomeCov(filename)
    stats = bed.get_stats("dataframe")
    return stats[list(stats.keys())[0]]

def get_bam_stats(filename):
    from sequana import BAM
    import pandas as pd
    bam = BAM(filename)
    stats = bam.get_stats()
    df = pd.Series(stats).to_frame().T
    return df

def main(args=None):

    if args is None:
        args = sys.argv[:]

    user_options = Options(prog="sequana")

    print("the usage of the summary tool may change significantly in the future")

    # If --help or no options provided, show the help
    if len(args) == 1:
        user_options.parse_args(["prog", "--help"])
    else:
        options = user_options.parse_args(args[1:])
    options.verbose = not options.quiet


    if options.multiple is True:
        from sequana.reporting.report_multiple_summary import SequanaMultipleSummary
        if options.glob:
            sms = SequanaMultipleSummary(pattern=options.glob, verbose=options.verbose)
        else:
            sms = SequanaMultipleSummary(verbose=options.verbose)
        sms.create_report()
        if options.verbose:
            print("Done. ")
        sys.exit(0)

    # We put the import here to make the --help faster
    if options.file:
        options.glob = options.file

    from easydev import MultiProcessing
    from sequana.snaketools import FileFactory

    ff = FileFactory(options.glob)
    assert len(set(ff.extensions)) == 1, "Input files must have the same extensions"
    extension = ff.all_extensions[0]

    print("Found %s files:" % len(ff.realpaths))
    for this in ff.realpaths:
        print(" - " + this)


    mc = MultiProcessing(options.thread, progress=True)
    if extension in ["fastq", "fastq.gz"]:
        for filename in ff.realpaths:
            mc.add_job(get_fastq_stats, filename, options.sample)

    elif extension.endswith("bed"):
        for filename in ff.realpaths:
            mc.add_job(get_bed_stats, filename)

    elif extension.endswith("bam"):
        for filename in ff.realpaths:
            mc.add_job(get_bam_stats, filename)

    mc.run()

    results = {}
    for i, this in enumerate(ff.filenames):
        if i == 0:
            df = mc.results[0]
            df.index.name = this
        else:
            other = mc.results[i]
            other.index.name = this
            df = df.append(other)

        # For the bed files only
        results[this] = mc.results[i]


    # For FastQ only
    try:df.index = ff.filenames
    except:pass

    # For the bed files only
    try:
        df = pd.concat([this.set_index("name").Value for this in results.values()], axis=1)
        df.columns = [i for i in range(len(results))]
    except Exception as err:
        print(err)

    print()
    print(df)
    return df

if __name__ == "__main__":
   import sys
   main()#sys.argv)

