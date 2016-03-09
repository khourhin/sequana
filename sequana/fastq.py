"""
IDEA

zcat test.fastq.gz | python filter ^ACGT | gzip > fitlered.fastq.gz

import re
query=re.compile("^ACGT")
if query.search(sequence):
    write(sequence)

Interesting as well for creating a generic zipfile opener

http://www.genomearchitecture.com/2014/01/how-to-gunzip-on-the-fly-with-python

"""
import io
import time
import zlib
from itertools import islice
import gzip
import subprocess

import numpy as np
import pandas as pd
from easydev import do_profile, Progress
import pylab

try:
    from itertools import izip_longest
except:
    from itertools import zip_longest as izip_longest

# for filter fastq files. see below
def grouper(iterable):
    args = [iter(iterable)] * 4
    return izip_longest(*args)



class Read(object):
    def __init__(self, data):
        pass
        # input could be a dictionary
        self.identifier = 1
        self.quality = 1
        self.sequence = 1


class Identifier(object):

    def __init__(self, identifier, version=None):
        self.identifier = identifier
        if version is None:
            self.version = self._infer_version()
        else:
            self.version = version
        self.info = self._interpret()

    def _interpret(self):
        if self.version == "Illumina_1.8+":
            return self._interpret_illumina_1_8()
        elif self.version == "Illumina_1.4+":
            return self._interpret_illumina_1_8()
        else:
            return {'identifier': self.identifier[:]}

    def _infer_version(self):
        """

    old illumina # is followed by 0 for no indexing but appear to use #NNNNNN for multiplex ID::

            @HWUSI-EAS100R:6:73:941:1973#0/1

        New Illumina (e.g., 1.8)::

            @EAS139:136:FC706VJ:2:2104:15343:197393 1:Y:18:ATCACG


        NCBI ::

            @FSRRS4401BE7HA [length=395] [gc=36.46] [flows=800] [phred_min=0] \
                                           [phred_max=40] [trimmed_length=95]

http://support.illumina.com/help/SequencingAnalysisWorkflow/Content/Vault/Informatics/Sequencing_Analysis/CASAVA/swSEQ_mCA_FASTQFiles.htm

        """
        if self.identifier.count(b':') == 4:
            left, right = self.identifier.rsplit(b":", 1)
            if right.count(b"#") == 1 and right.count(b"\\") == 1:
                return "Illumina_1.4+"


        if self.identifier.count(b" ") == 1:
            left, right = self.identifier.split(b" ")
            if left.count(b':') == 6 and right.count(b':') == 3:
                return "Illumina_1.8+"

        return "Custom or Unknown identifier"

    def _interpret_illumina_1_8(self):
        """

        @EAS139:136:FC706VJ:2:2104:15343:197393 1:Y:18:ATCACG

        Note the space and : separators
        """
        assert self.identifier.startswith(b"@")
        # skip @ character
        identifier = self.identifier[1:]
        # replace spaces by : character
        identifier = b' '.join(identifier.split())
        identifier = identifier.replace(b' ', b':')
        items = identifier.split(b':')
        if len(items) != 11:
            raise ValueError('Niumber of items in the identifier should be 11')
        res = {}
        res['identifier'] = self.identifier[:]
        res['instrument'] = items[0]
        res['run_id'] = items[1]
        res['flowcell_id'] = items[2]
        res['flowcell_lane'] = items[3]
        res['tile_number'] = items[4]
        res['x_coordinate'] = items[5]
        res['y_coordinate'] = items[6]
        res['member_pair'] = items[7]
        res['filtered'] = items[8]
        res['self._control_bits'] = items[9]
        res['index_sequence'] = items[10]
        return res

    def _interpret_illumina_1_4(self):
        # skip @ character
        identifier = self.identifier[1:]
        identifier = identifier.replace('#', ':')
        identifier = identifier.replace('/', ':')
        items = identifier.split(':')

        if len(items) != 7:
            raise ValueError('Number of items in the identifier should be 7')
        # ['@HWUSI-EAS100R', '6', '73', '941', '1973#0/1']
        res['identifier'] = self.identifier[:]
        res['instrument_name'] = items[0]
        res['flowcell_lane'] = items[1]
        res['tile_number'] = items[2]
        res['self._x_coordinate'] = items[3]
        res['self._y_coordinate'] = items[4]
        res['self._index'] = '#' + items[5]
        res['self._member_pair'] = '/' + items[6]

    def __str__(self):
        txt = ""
        for key in sorted(self.info.keys()):
            txt += '%s: %s\n' % (key, self.info[key])
        return txt

    def __repr__(self):
        return "Identifier (%s)" % self.version



class FastQ(object):
    """

    extract first 100k lines

    f = FastQ("")
    f.extract_head(100000, output='test.fastq')
    f.extract_head(100000, output='test.fastq.gz')

    equivalent to

    zcat myreads.fastq.gz | head -100000 | gzip > test100k.fastq.gz


    Counts the number of lines ::

        f.count_lines()

    or reads (assuming 4 lines per read)::

        f.count_reads()

    Features to implement::
        - filter out short / long reads
        - filter out reads with NNN
        - filter out low quality end reads
        - cut poly A/T tails

        - dereplicate seauences
        - split multiplex
        - remove contaminants
        - compact fastq
        - convert to/from sff
        - convert to fasta
    """
    def __init__(self, filename, verbose=False):

        self.filename = filename
        self.verbose = verbose
        self._count_reads = None
        self._count_lines = None
        
        # opens the file in read mode
        self.__enter__()
        # Can we identify the type of data ?
        try:
            self.identifier = Identifier(self.next()["identifier"])
            self.rewind()
            self.data_format = self.identifier.version
        except:
            self.data_format = "unknown"

    def _get_count_reads(self):
        if self._count_reads is None:
            self._count_reads = self.count_reads()
        return self._count_reads
    n_reads = property(_get_count_reads, doc="return number of reads")

    def _get_count_lines(self):
        if self._count_lines is None:
            self._count_lines = self.count_lines()
        return self._count_lines
    n_lines = property(_get_count_lines,
        doc="return number of lines (should be 4 times number of reads)")

    def __len__(self):
        return self.n_reads

    def rewind(self):
        nreads = self._count_reads
        self._fileobj.close()
        self.__enter__()
        self._count_reads = nreads

    def count_reads_gz(self, CHUNKSIZE=65536):
        # this is fast. On a 63M reads, takes 21 seconds as
        # compared to 46 s (real) and 1.13 (user) with zcat | wc
        # wc seems slow (same effects with uncompressde file).
        # Using gzip.open and reading lines is slower by a factor 10
        # hints from http://wiki.glitchdata.com/index.php?title=Python:_File_Compression_and_Decompression

        # cannot be re-used so must be written here and wherever decompression is
        # required
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        with open(self.filename, 'rb') as f:
            buf = f.read(CHUNKSIZE)
            count = 0
            while buf:
                outstr = d.decompress(buf)
                count += outstr.count(b"\n")
                buf = f.read(CHUNKSIZE)
        return count

    def count_lines(self):
        """Return number of lines

        This is 40 times faster than wc on uncompressed file and
        3-4 times faster on zipped file (using gunzip -c file | wc -l)
        """
        if self.filename.endswith("gz"):
            count = self.count_reads_gz()
        else:
            count = self._count_reads_buf()
        return count

    def count_reads(self):
        nlines = self.count_lines()
        if divmod(nlines, 4)[1] != 0:
            print("WARNING. number of lines not multiple of 4.")
        return nlines / 4

    def _count_reads_buf(self, block=1024*1024):
        # 0.12 seconds to read 3.4M lines, faster than wc command
        # on 2M reads, takes 0.1 seconds whereas wc takes 1.2 seconds
        lines = 0
        with open(self.filename, 'rb') as f:
            buf = f.read(block)
            while buf:
                lines += buf.count(b'\n')
                buf = f.read(block)
        return lines

    def extract_head(self, N, output_filename):
        # extract N lines

        # equivalent to
        # zcat input.fasta | head -400000 > out.fasta
        # 3 times slower than cat file | head -1000000 > test.fastq
        # but remains pretty fast (0.5 seconds for 2M reads).
        # todo: compress the file
        if self.filename.endswith(".gz"):
            self._extract_head_gz(N, output_filename)
        else:
            self._extract_head(N, output_filename)

    def _extract_head(self, N, output_filename):
        with open(self.filename, 'r') as fin:
            if output_filename.endswith("gz"):
                output_filename_nogz = output_filename.replace(".gz", "")

                with open(output_filename_nogz, 'w') as fout:
                    fout.writelines(islice(fin, N))

                # compress the file
                self._gzip(output_filename_nogz)

            else:
                with open(output_filename, 'w') as fout:
                    fout.writelines(islice(fin, N))

    def _gzip(self, filename):
        try:
            s = subprocess.Popen(["pigz", "-f", filename])
            s.wait()
        except:
            s = subprocess.Popen(["gzip", filename, "-f"])
            s.wait()

    def _extract_head_gz(self, N, output_filename="test.fastq.gz", level=6, CHUNKSIZE=65536):
        """

        if output not compressed, this is 20% faster than
        "zcat file | head -1000000 > output.fastq

        If output is compressed, this is equivalent to :
        "zcat file | head -1000000 | gzip > output.fastq

        Tested under Python 2.7 , Linux box.
        """
        # make sure N is integer
        N = int(N)

        # as fast as zcat file.fastq.gz | head -200000 > out.fasta

        # this is to supress the header
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)

        # will we gzip the output file ?
        output_filename, tozip = self._istozip(output_filename)

        with open(self.filename, 'rb') as fin:
            buf = fin.read(CHUNKSIZE)
            count = 0

            with open(output_filename, "wb") as fout:
                while buf:
                    outstr = d.decompress(buf)
                    count += outstr.count(b"\n")
                    if count > N:
                        # there will be too many lines, we need to select a subset
                        missing = count - N
                        outstr = outstr.strip().split(b"\n")
                        NN = len(outstr)
                        outstr = b"\n".join(outstr[0:NN-missing-1]) + b"\n"
                        fout.write(outstr)
                        break
                    fout.write(outstr)
                    buf = fin.read(CHUNKSIZE)

        if tozip is True: self._gzip(output_filename)
        return count

    def _istozip(self, filename):
        if filename.endswith('.gz'):
            tozip = True
            filename = filename.split(".gz",1)[0]
        else:
            tozip = False
        return filename, tozip

    def select_random_reads(self, N, output_filename):
        if output_filename.endswith(".gz"):
            self._select_random_reads()
        else:
            self._select_random_reads_gz()

    def _select_random_reads(self, N, output_filename):
        pass

    def _select_random_reads_gz(self, N, output_filename):
        raise NotImplementedError
        n_reads = self.count_reads()
        if n_reads > self.count_reads():
            # nothing to do except a copy
            pass
        else:
            import random
            for i in random.sample(xrange(N)):
                pass

    def split_lines(self, N=100000, gzip=True):
        if self.filename.endswith(".gz"):
            outputs = self._split_lines_gz(N, gzip=gzip)
        else:
            outputs = self._split_lines(N, gzip=gzip)
        return outputs

    def _split_lines_gz(self, N, gzip=True, CHUNKSIZE=65536):
        # split input in N files
        # There is a split function under Unix but (1) not under windows
        # and (2) split a gzip into N chunks or n lines will split the
        # reads in the middle. So, we want to unzip, select N lines (or chunks)
        # and zip each chunk.
        self._check_multiple(N)
        N_chunk, remainder = divmod(self.n_lines, N)
        if remainder > 0:
            N_chunk += 1

        # let prepare some data first. Let us build the filenames once for all
        outputs = []
        for i in range(0, N_chunk):
            lb = (i ) * N + 1
            ub = (i + 1) * N
            if ub > self.n_lines:
                ub = self.n_lines

            if self.filename.endswith(".gz"):
                input_filename = self.filename.split(".gz")[0]
                output_filename = input_filename
            else:
                input_filename = self.filename
                output_filename = self.filename
            output_filename.split(".", -1)
            left, right = input_filename.rsplit(".", 1)
            output_filename = left + "_%s_%s." % (lb, ub) + right
            outputs.append(output_filename)

        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        with open(self.filename, 'rb') as fin:
            # init buffer
            buf = fin.read(CHUNKSIZE)
            count = 0

            # open an output file handler
            current_file_counter = 0
            fout = open(outputs[0], "wb")

            while buf:
                outstr = d.decompress(buf)
                count += outstr.count(b"\n")
                if count > N:
                    # if too many lines were read, fill the current file
                    # and keep remaining data (skip the reading of new
                    # data for now)
                    missing = count - N
                    outstr = outstr.strip().split(b"\n")
                    NN = len(outstr)
                    # we need to split the buffer into the part to save
                    # in this file and the part to save in the next file later
                    # on (remaining)
                    # Note that there is no '\n' added here because we do not
                    # read lines that we may end up in the middle of a line
                    remaining  = b"\n".join(outstr[NN-missing-1:])
                    # whereas here, we are at the end of a line
                    outstr = b"\n".join(outstr[0:NN-missing-1]) + b"\n"
                    # write and close that file
                    fout.write(outstr)
                    fout.close()
                    # and open the next one where we can already save the end of
                    # the buffer
                    current_file_counter += 1
                    fout = open(outputs[current_file_counter], "wb")
                    fout.write(remaining)
                    # we need to keep track of what has be written
                    count = remaining.count(b'\n')
                    # and finally we can now read a new chunk of data
                    buf = fin.read(CHUNKSIZE)
                else:
                    fout.write(outstr)
                    buf = fin.read(CHUNKSIZE)

        if gzip is True:
            for output in outputs:
                self._gzip(output)
            outputs = [x + ".gz" for x in outputs]
        return outputs

    def split_chunks(self, N=10):
        # split per chunks of size N
        pass

    def _check_multiple(self, N, multiple=4):
        if divmod(N, multiple)[1] != 0:
            msg = "split_lines method expects a multiple of %s." %multiple
            raise ValueError(msg)

    # This could be part of easydev or other software
    def _split_lines(self, N, gzip=True):
        # split input in N files
        # We will name them with reads number that is
        # filename.fastq gives for example:
        # --> filename_1_100000.fastq
        # --> filename_100001_151234.fastq
        self._check_multiple(N)

        assert type(N) == int
        if N >= self.n_lines:
            print("Nothing to do. Choose a lower N value")
            return

        outputs = []
        N_chunk, remainder = divmod(self.n_lines, N)

        with open(self.filename) as fin:
            for i in range(0, N_chunk):
                lb = (i ) * N + 1
                ub = (i + 1) * N
                output_filename = self.filename
                output_filename.split(".", -1)
                left, right = self.filename.rsplit(".", 1)
                output_filename = left + "_%s_%s." % (lb, ub) + right
                outputs.append(output_filename)
                with open(output_filename, 'w') as fout:
                    fout.writelines(islice(fin, N))
            # last chunk is dealt with outside the loop
            lb = ub + 1
            ub = self.n_lines
            output_filename = left + "_%s_%s." % (lb, ub) + right
            if remainder !=0:
                outputs.append(output_filename)
                with open(output_filename, 'w') as fout:
                    fout.writelines(islice(fin, remainder))

        if gzip is True:
            for output in outputs:
                self._gzip(output)
            outputs = [x + ".gz" for x in outputs]
        return outputs

    def split_chunks(self, N=10):
        # split per chunks of size N
        pass

    def random(self, N=10000, output_filename="test.fastq",
               bp=50, quality=40):
        """
        N here is the number of reads
        """
        # a completely random fastq
        from .phred import quality
        with open(output_filename, "wb") as fh:
            count = 1
            template = "@Insilico\n"
            template += "%(sequence)\n"
            template += "+\n"
            template += "%s(quality)\n"
            fh.writelines(template % {
                'sequence': "".join(["ACGT"[random.randint(0,3)] for this in xrange(bp)]),
                'quality': "".join()})
        # quality could be q function for a distribution

    def joining(self, pattern, output_filename):
        """

        zcat Block*.fastq.gz | gzip > combined.fastq.gz

        """
        raise NotImplementedError


    def __iter__(self):
       return self

    def __exit__(self, type, value, traceback):
        try:
            self._fileobj.close()
        except AttributeError:
            pass
        finally:
            self._fileobj.close()

    def __enter__(self):
        fh = open(self.filename, "rb")
        if self.filename.endswith('.gz'):
            self._fileobj = gzip.GzipFile(fileobj=fh)
        else:
            self._fileobj = fh
        return self

    def __next__(self): # python 3
        return self.next()

    def next(self): # python 2
        # reads 4 lines
        d = {}
        try:
            """data = islice(self._fileobj, 4)
            d['identifier'] = next(data).strip()
            d['sequence'] = next(data).strip()
            skip = next(data)
            d['quality'] = next(data).strip()
            """

            # 15% faster than islice + next
            d['identifier'] = self._fileobj.readline().strip()
            d['sequence'] = self._fileobj.readline().strip()
            temp = self._fileobj.readline()
            d['quality'] = self._fileobj.readline().strip()

            # can be faster but slower on average
            """d['identifier'] = self._fileobj.readlines(1)[0].strip()
            d['sequence'] = self._fileobj.readlines(1)[0].strip()
            self._fileobj.readlines(1)
            d['quality'] = self._fileobj.readlines(1)[0].strip()
            """
            # Somehow the readlines still return "" even if the end of file is
            # reached
            if temp == "":
                raise StopIteration
        except KeyboardInterrupt:
            self._fileobj.close()
            self.__enter__()
        except:
            self.rewind()
            raise StopIteration

        return d

    def __getitem__(self, index):
        return 1

    def filter(self, identifiers_list=[], min_bp=None, max_bp=None,
        progressbar=True, output_filename='filtered.fastq', remove=True):
        #7 seconds without identifiers to scan the file
        # on a 750000 reads

        if min_bp is None:
            min_bp = 1e9

        if max_bp is None:
            max_bp = -1

        # make sure we are at the beginning
        self.rewind()

        output_filename, tozip = self._istozip(output_filename)

        with open(output_filename, "w") as fout:
            pb = Progress(self.n_reads)
            buf = ""
            filtered = 0

            for count, lines in enumerate(grouper(self._fileobj)):
                identifier = lines[0].split()[0]
                if lines[0].split()[0] in identifiers_list:
                    filtered += 1 
                else:
                    buf += "%s%s+\n%s" % (lines[0], lines[1], lines[3])
                    if count % 100000 == 0:
                        fout.write(buf)
                        buf = ""
                pb.animate(count+1)
            fout.write(buf)
            print(filtered)
            if filtered < len(identifiers_list):
                print("\nWARNING: not all identifiers were found in the fastq file to " +
                      "be filtered.")
        if tozip is True: self._gzip(output_filename)


class FastQMerger(object):
    def __init__(self, filenames):
        self.filenames = filenames

    def save(self):
        pass

# a simple decorator to check whether the data was computed or not.
# If not, compute it
def run_info(f):
    def wrapper(*args):
        #args[0] is the self of the method
        try:
            args[0].gc_content
        except:
            args[0].get_info()
        return f(*args)
    return wrapper

class FastQC(object):
    def __init__(self, filename, sample=500000):
        self.fastq = FastQ(filename)

        N = self.fastq.count_reads()
        if N < sample:
            self.sample = N
        else:
            self.sample = sample

        self.summary = {}
        self.fontsize = 16

    def get_info(self):
        from . import phred
        N = self.fastq.count_reads()
        qualities = []
        mean_qualities = []
        sequences = []
        minimum = 1e6
        maximum = 0
        lengths = []
        self.gc_list = []
        self.nucleotides = 0
        self.N_list = []

        self.identifiers = []
        pb = Progress(self.sample)

        # could use multiprocessing
        for i, record in enumerate(self.fastq):
            # keep track of min/max sequence length
            N = len(record['sequence'])
            if N < minimum:
                minimum = N
            if N > maximum:
                maximum = N
            self.nucleotides += N

            quality = phred.Quality(record['quality']).quality
            qualities.append(quality)
            mean_qualities.append(pylab.mean(quality))
            if i > self.sample:
                break

            identifier = Identifier(record['identifier'])
            self.identifiers.append(identifier.info)

            sequence = record['sequence']
            sequences.append(sequence)

            GC = sequence.count(b'G') + sequence.count(b'C')
            self.gc_list.append(GC)
            self.N_list.append(sequence.count(b'N'))

            pb.animate(i+1)

        self.tiles = {}
        self.tiles['x'] = [float(this['x_coordinate']) for this in self.identifiers]
        self.tiles['y'] = [float(this['y_coordinate']) for this in self.identifiers]
        self.tiles['tiles'] = [this['tile_number'] for this in self.identifiers]

        self.gc_content = sum(self.gc_list) / float(self.nucleotides)
        self.qualities = qualities
        self.mean_qualities = mean_qualities
        self.minimum = minimum
        self.maximum = maximum
        self.sequences = sequences

        print('\nCreating tiles data')
        import collections
        d = collections.defaultdict(list)
        for tile, seq in zip(self.tiles['tiles'], self.qualities):
            d[tile].append(seq)
        self.data_imqual = [pd.DataFrame(d[key]).mean().values for key in sorted(d.keys())]

    @run_info
    def imshow_qualities(self):
        from biokit.viz import Imshow
        im = Imshow(self.data_imqual)
        im.plot(xticks_on=False, yticks_on=False, origin='lower')
        pylab.title("Quality per tile", fontsize=self.fontsize)
        pylab.xlabel("Position in read (bp)")
        pylab.ylabel("tile number")

    @run_info
    def boxplot_quality(self):
        df = pd.DataFrame(self.qualities)
        from biokit.viz.boxplot import Boxplot
        bx = Boxplot(df)
        bx.plot()

    @run_info
    def histogram_sequence_coordinates(self):
        # Distribution of the reads in x-y plane
        # less reads on the borders ?
        from biokit.viz.hist2d import Hist2D
        Hist2D(self.tiles['x'], self.tiles['y']).plot()

    @run_info
    def histogram_sequence_lengths(self):
        data = [len(x) for x in self.sequences]
        bins = self._get_xbins()
        pylab.hist(data, bins=bins)
        pylab.grid()
        pylab.xlabel("position bp", fontsize=self.fontsize)

    @run_info
    def _get_xbins(self):
        if self.maximum<40:
            bins = range(1,41)
        else:
            bins = range(1,10) + range(10,self.maximum + 1, 5)
        return bins

    @run_info
    def histogram_gc_content(self):
        pylab.hist(self.gc_list, bins=range(0, self.maximum))
        pylab.grid()
        pylab.title("GC content distribution over all sequences")
        pylab.xlabel("Mean GC content (\%)", fontsize=self.fontsize)


