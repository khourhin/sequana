import sequana.featurecounts as fc
from sequana import sequana_data


def test_featurecounts():
    RNASEQ_DIR_0 = sequana_data("featurecounts") + "/rnaseq_0"
    RNASEQ_DIR_1 = sequana_data("featurecounts") + "/rnaseq_1"
    RNASEQ_DIR_2 = sequana_data("featurecounts") + "/rnaseq_2"
    RNASEQ_DIR_undef = sequana_data("featurecounts") + "/rnaseq_undef"
    RNASEQ_DIR_noconsensus = sequana_data("featurecounts") + "/rnaseq_noconsensus"

    assert fc.get_most_probable_strand_consensus(RNASEQ_DIR_0, tolerance=0.1) == "0"
    assert fc.get_most_probable_strand_consensus(RNASEQ_DIR_1, tolerance=0.1) == "1"
    assert fc.get_most_probable_strand_consensus(RNASEQ_DIR_2, tolerance=0.1) == "2"

    assert (
        fc.get_most_probable_strand_consensus(RNASEQ_DIR_undef, tolerance=0.1) == "NA"
    )

    try:
        fc.get_most_probable_strand_consensus(RNASEQ_DIR_noconsensus, tolerance=0.1)
        assert False
    except IOError:
        assert True
