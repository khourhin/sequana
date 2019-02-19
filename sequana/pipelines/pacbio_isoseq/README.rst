:Overview:
:Input: A set of BAM files (subreads.bam from Pacbio sequencer)
:Output:

Usage
~~~~~~~

::

    sequana --pipeline pacbio_isoseq --input-directory Data_test/ --working-directory analysis --extension bam --no-adapters
    snakemake -s pacbio_isoseq.rules --stats stats.txt -p -j 12 --nolock

Or use :ref:`sequanix_tutorial` interface.

Requirements
~~~~~~~~~~~~~~~~~~

.. include:: ../sequana/pipelines/pacbio_isoseq/requirements.txt

.. image:: https://raw.githubusercontent.com/sequana/sequana/master/sequana/pipelines/pacbio_isoseq/dag.png


Details
~~~~~~~~~

This pipeline is used
Rules and configuration details
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a documented configuration


FastQC
^^^^^^^^^^^
.. snakemakerule:: fastqc_dynamic

