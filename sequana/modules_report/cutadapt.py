# coding: utf-8
#
#  This file is part of Sequana software
#
#  Copyright (c) 2016 - Sequana Development Team
#
#  File author(s):
#      Thomas Cokelaer <thomas.cokelaer@pasteur.fr>
#      Dimitri Desvillechabrol <dimitri.desvillechabrol@pasteur.fr>,
#          <d.desvillechabrol@gmail.com>
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
"""Module to write coverage report"""
import os
import io

from sequana.modules_report.base_module import SequanaBaseModule
from sequana.utils import config

from sequana.lazy import pandas as pd
from sequana.lazy import pylab
from sequana import logger

from sequana.utils.datatables_js import DataTable


class CutadaptModule(SequanaBaseModule):
    """ Write HTML report of coverage analysis. This class takes either a
    :class:`GenomeCov` instances or a csv file where analysis are stored.
    """
    def __init__(self, cutadapt_log, sample_name):
        """
        :param input: 
        """
        super().__init__()
        # Expected input data is the cutadapt log file
        if os.path.exists(cutadapt_log) is False:
            logger.error("This file {} does not exists".format(cutadapt_log))
        self.input_filename = cutadapt_log
        self.sample_name = sample_name

        self.jinja = {}

        self.read_data()
        self.parse()
        self.create_report_content()
        self.create_html("cutadapt.html")

    def create_report_content(self):
        """ Generate the sections list to fill the HTML report.
        """
        self.sections = list()
        self.add_summary_section()
        self.add_stat_section()
        self.add_adapters_section()
        self.add_histogram_section()
        self.add_log_section()

    def read_data(self):
        with open(self.input_filename, "r") as fin:
            self._rawdata = fin.read()
            if "Total read pairs processed" in self._rawdata:
                self.jinja['mode'] = "Paired-end"
                self.mode = "pe"
            else:
                self.jinja['mode'] = "Single-end"
                self.mode = "se"
 
    def _get_data_tobefound(self):
        tobefound = []
        if self.mode == 'se':
            tobefound.append(('total_reads', 'Total reads processed:'))
            tobefound.append(('reads_with_adapters', 'Reads with adapters:'))
            tobefound.append(('reads_too_short', 'Reads that were too short:'))
            tobefound.append(('reads_kept', 'Reads written (passing filters):'))
        else:
            # ! spaces are probably import here below !
            tobefound.append(('paired_total_reads', 'Total read pairs processed:'))
            tobefound.append(('paired_reads1_with_adapters', '  Read 1 with adapter:'))
            tobefound.append(('paired_reads2_with_adapters', '  Read 2 with adapter:'))
            tobefound.append(('paired_reads_too_short', 'Pairs that were too short'))
            tobefound.append(('paired_reads_kept', 'Pairs written (passing filters):'))
        return tobefound

    def add_log_section(self):
        self.sections.append({
            "name": "log",
            "anchor": "log",
            "content": "<pre>\n"+ self._rawdata + "</pre>\n"
        })

    def add_stat_section(self):
        if self.mode == "pe":
            prefix = "paired_"
        else:
            prefix = ""

        df = pd.DataFrame({'Number of reads': [], 'percent': []})
        df.ix['Total paired reads'] = [
                   self.jinja['%stotal_reads' % prefix],
                   '(100%)']
        if self.mode == "pe":
            df.ix['Read1 with adapters'] = [
                   self.jinja['%sreads1_with_adapters' % prefix],
                   self.jinja['%sreads1_with_adapters_percent'% prefix]]
            df.ix['Read2 with adapters'] = [
                   self.jinja['%sreads2_with_adapters' % prefix],
                   self.jinja['%sreads2_with_adapters_percent'% prefix]]
        else:
            df.ix['Pairs with adapters'] = [
                   self.jinja['%sreads_with_adapters' % prefix],
                   self.jinja['%sreads_with_adapters_percent'% prefix]]
        df.ix['Pairs too short'] = [
                   self.jinja['%sreads_too_short' % prefix],
                   self.jinja['%sreads_too_short_percent'% prefix]]
        df.ix['Pairs kept'] = [
                   self.jinja['%sreads_kept' % prefix],
                   self.jinja['%sreads_kept_percent' % prefix]]
        if self.mode != "pe":
            df.index = [this.replace("paired", "").replace("Pairs", "Reads") for this in df.index]

        #df.to_json(self.sample_name + "/cutadapt/cutadapt_stats1.json")
        datatable = DataTable(df, "cutadapt", index=True)
        datatable.datatable.datatable_options = {
            'scrollX': '300px',
            'pageLength': 15,
            'scrollCollapse': 'true',
            'dom': 'Brtp',
            "paging": "false",
            'buttons': ['copy', 'csv']}
        js = datatable.create_javascript_function()
        html_tab = datatable.create_datatable(float_format='%.3g')
        #csv_link = self.create_link('link', self.filename)
        #vcf_link = self.create_link('here', 'test.vcf')

        self.sections.append({
            "name": "Stats",
            "anchor": "stats",
            "content": "<p>{} {}</p>".format(html_tab, js)
        })

    def add_adapters_section(self):
        # Create a Table with adapters
        df = pd.DataFrame()
        df = pd.DataFrame({'Length': [], 'Trimmed':[], 'Type':[], 'Sequence': [], })

        for count, adapter in enumerate(self.data['adapters']):
            name = adapter['name']
            info = adapter['info']
            df.ix[name] = [info['Length'], info['Trimmed'],
                info['Type'], info['Sequence']]
        df.columns = ['Length', 'Trimmed', 'Type', 'Sequence']
        df['Trimmed'] = df.Trimmed.map(lambda x: int(x.replace("times.", "")))

        # df.to_json(self.sample_name + "/cutadapt/cutadapt_stats2.json")
        df.sort_values(by="Trimmed", ascending=False, inplace=True)


        datatable = DataTable(df, "adapters", index=True)
        datatable.datatable.datatable_options = {
            'scrollX': 'true',
            'pageLength': 15,
            'scrollCollapse': 'true',
            'dom': 'Bfrtip',
            'buttons': ['copy', 'csv']}
        js = datatable.create_javascript_function()
        html_tab = datatable.create_datatable(float_format='%.3g')
        #h = reports.HTMLTable(df)
        #html = h.to_html(index=True)
        self.jinja['adapters'] = "tralala"
        self.sections.append({
            "name": "Adapters",
            "anchor": "adapters",
            "content": "<p>{} {}</p>".format(html_tab, js)
        })

    def add_summary_section(self):
        """ Coverage section.
        """
        #image = self.create_embedded_png(self.chromosome.plot_coverage,
        #                              input_arg="filename")

        import textwrap
        command = "\n".join(textwrap.wrap(self.jinja['command'], 80))
        command = self.jinja['command']

        html = "<p>Data type: {}  </p>".format(self.jinja["mode"])
        html += '<div style="textwidth:80%">Command: <pre>{}</pre></div>'.format(command)
        self.sections.append({
            "name": "Data and command used",
            "anchor": "cutadapt",
            "content": html
        })

    def add_histogram_section(self):
        """Show only histograms with at least 3 counts

        """
        # This would work for cutadapt only
        histograms = self._get_histogram_data()
        html = ""
        html += "<div>\n"

        # get keys and count; Sort by number of adapters removed.
        # TODO: could have reused the df
        adapter_names = list(histograms.keys())
        count = [histograms[k]['count'].sum() for k in adapter_names]
        df2 = pd.DataFrame({'key':adapter_names, "count": count})
        df2.sort_values(by="count", ascending=False, inplace=True)

        for count, key in zip(df2["count"], df2['key']) :
            if len(histograms[key]) <= 3:
                continue

            def plotter(filename, key):
                name = key.replace(" ", "_")
                pylab.ioff()
                histograms[key].plot(logy=False, lw=2, marker="o")
                pylab.title(name + "(%s)" % count)
                pylab.grid(True)
                pylab.savefig(filename)
            imagehtml = self.create_embedded_png(plotter, "filename",
                style='width:45%', key=key)
            html += imagehtml
        html += "</div>\n"

        self.jinja['cutadapt'] = html
        self.sections.append({
            "name": "Histogram",
            "anchor": "histogram",
            "content":  "<p>Here are the most representative/significant adapters found in the data</p>"+ html
        })

    def parse(self):
        d = {}
        # output
        tobefound = self._get_data_tobefound()
        adapters = []
        self.data = {}

        data = self._rawdata.splitlines()
        # some metadata to extract
        for this in tobefound:
            key, pattern = this
            found = [line for line in data if line.startswith(pattern)]
            if len(found) == 0:
                print("ReportCutadapt: %s (not found)" % pattern)
            elif len(found) == 1:
                text = found[0].split(":", 1)[1].strip()
                try:
                    this, percent = text.split(" ")
                    self.jinja[key] = this
                    self.jinja[key+'_percent'] = percent
                except:
                    self.jinja[key] = text
                    self.jinja[key+'_percent'] = "?"

        dd = {}
        positions = []
        for pos, this in enumerate(data):
            if this.startswith("Command line parameters: "):
                cmd = this.split("Command line parameters: ")[1]
                self.jinja['command'] = "cutadapt " + cmd
            if this.startswith("=== ") and "Adapter" in this:
                name = this.split("=== ")[1].split(" ===")[0].strip()
                dd['name'] = name
                continue
            if this.startswith('Sequence:'):
                info = this.split("Sequence:", 1)[1].strip()
                info = info.split(";")
                dd['info'] = {
                    'Sequence': info[0].strip(),
                    'Type': info[1].split(':',1)[1].strip(),
                    'Length': info[2].split(':',1)[1].strip(),
                     'Trimmed': info[3].split(':',1)[1].strip()
                }
                adapters.append(dd.copy())
        self.data["adapters"] = adapters

    def _get_histogram_data(self):
        """In cutadapt logs, an adapter section contains
        an histogram of matches that starts with a header
        and ends with a blank line
        """
        header = 'length\tcount\texpect\tmax.err\terror counts\n'
        with open(self.input_filename, 'r') as fin:
            # not too large so let us read everything
            data = fin.readlines()
            scanning_histogram = False
            adapters = []
            current_hist = header
            dfs = {}

            if "variable 5'/3'" in "\n".join(data):
                cutadapt_mode = "b"
            else:
                cutadapt_mode = "other"

            for this in data:
                # while we have not found a new adapter histogram section,
                # we keep going
                # !! What about 5' / 3' 
                if this.startswith("==="):
                    if 'read: Adapter' in this:
                        # We keep read: Adatpter because it may be the first
                        # or second read so to avoid confusion we keep the full 
                        # name for now.
                        name = this.replace("First read: Adapter ", "R1_")
                        name = name.replace("Second read: Adapter ", "R2_")
                        name = name.strip().strip("===")
                        name = name.strip()
                    elif "=== Adapter" in this:
                        name = this.split("=== ")[1].split(" ===")[0]
                        name = name.strip()
                    else:
                        pass

                if scanning_histogram is False:
                    if this == header:
                        # we found the beginning of an histogram
                        scanning_histogram = True
                    else:
                        # we are somewhere in the log we do not care about
                        pass
                elif scanning_histogram is True and len(this.strip()) != 0:
                    # accumulate the histogram data
                    current_hist += this
                elif scanning_histogram is True and len(this.strip()) == 0:
                    # we found the end of the histogram
                    # Could be a 5'/3' case ? if so another histogram is
                    # possible
                    self.dd = current_hist
                    df = pd.read_csv(io.StringIO(current_hist), sep='\t')
                    #reinitiate the variables
                    if cutadapt_mode != "b":
                        dfs[name] = df.set_index("length")
                        current_hist = header
                        scanning_histogram = False
                    else:
                        # there will be another histogram so keep scanning
                        current_hist = header
                        # If we have already found an histogram, this is
                        # therefore the second here.
                        if name in dfs:
                            dfs[name] = dfs[name].append(df.set_index("length"))
                            scanning_histogram = False

                            #Now that we have the two histograms, we can merge
                            # them using a group by

                            dfs[name] = dfs[name].reset_index().groupby("length").aggregate(sum)
                        else:
                            dfs[name] = df.set_index("length")
                            scanning_histogram = True

                            df.reset_index().groupby("length").aggregate(sum)
                else:
                    pass
        return dfs
