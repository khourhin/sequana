# coding: utf-8
#
#  This file is part of Sequana software
#
#  Copyright (c) 2020 - Sequana Development Team
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
"""Module to write differential regulation analysis report"""

from sequana.lazy import pandas as pd

from sequana.modules_report.base_module import SequanaBaseModule
from sequana.utils.datatables_js import DataTable
import os

class RNAdiffModule(SequanaBaseModule):
    """ Write HTML report of variant calling. This class takes a csv file
    generated by sequana_variant_filter.
    """
    def __init__(self, folder, design, gff,
                    output_filename="rnadiff.html", **kwargs):
        """.. rubric:: constructor

        """
        super().__init__()
        self.title = "RNAdiff"
        self.independent_module = True
        self.module_command = "--module rnadiff"

        from sequana.rnadiff import RNADiffResults

        self.rnadiff = RNADiffResults(folder, design, gff=gff, **kwargs)

        # nice layout for the report
        import seaborn
        seaborn.set()

        self.create_main_report_content()
        self.create_individual_reports()

        self.create_html(os.path.join(folder, output_filename))
        import matplotlib
        matplotlib.rc_file_defaults()

    def create_individual_reports(self):
        description = """<p>The differential analysis is based on DESeq2. This
tool aim at fitting one linear model per feature. Given the replicates in
condition one and the replicates in condition two, a p-value is computed to
indicate whether the feature (gene) is differentially expressed. Then, all
p-values are corrected for multiple testing.</p>

<p>It may happen that one sample seems unrelated to the rest. For every feature
and every model, Cook's distance is computed. It reflects how the sample matches
the model. A large value indicates an outlier count and p-values are not computed
for that feature.</p>
"""

        self.sections.append({
           "name": "6. DGE results",
            'anchor': 'filters_option',
            'content': description})

        counter = 1
        for name, comp in self.rnadiff.comparisons.items():
            self.add_individual_report(comp, name, counter)

    def create_main_report_content(self):
        self.sections = list()

        self.summary()
        self.add_plot_count_per_sample()
        self.add_cluster()
        self.add_normalisation()
        self.add_dispersion()

    def summary(self):
        """ Add information of filter.
        """
        Sdefault = self.rnadiff.summary()
        self.rnadiff.log2_fc = 1
        S1 = self.rnadiff.summary()

        # set options
        options = {
            'scrollX': 'true',
            'pageLength': 20,
            'scrollCollapse': 'true',
            'dom': '',
            'buttons': []}

        S = pd.concat([Sdefault, S1])

        N = len(Sdefault)
        df = pd.DataFrame({
            'comparison_link': [1] * len(S),
            'comparison': S.index.values,
            'Description': ['Number of DGE (any FC)']*N+ ['Number of DGE (|FC| > 1)']*N,
            'Down': S['down'].values, 
            'Up':  S['up'].values, 
            'Total': S['all'].values})
        df = df[['comparison', 'Description', 'Down', 'Up', 'Total', 'comparison_link']] 

        df['comparison_link'] = [f"#{name}_table_all" for name in Sdefault.index] + \
                                [f"#{name}_table_sign" for name in Sdefault.index] 

        dt = DataTable(df, 'dge')
        dt.datatable.set_links_to_column('comparison_link', 'comparison',
            new_page=False)
        dt.datatable.datatable_options = options
        js_all = dt.create_javascript_function()
        html = dt.create_datatable(float_format='%d')
        self.sections.append({
            'name': "Summary",
            'anchor': 'filters_option',
            'content':
                f"""<p>Here below is a summary of the Differential Gene
Expression (DGE) analysis. You can find two entries per comparison. The first
one has no filter except for an adjusted p-value of 0.05. The second shows the
expressed genes with a filter of the log2 fold change of 1 (factor 2 in a normal
scale). Clicking on any of the link will lead you to the section of the comparison. 
{js_all} {html} </p>"""})

    def add_dispersion(self):
        style = "width:65%"
        def dispersion(filename):
            import pylab
            pylab.ioff()
            pylab.clf()
            self.rnadiff.plot_dispersion()
            pylab.savefig(filename)
            pylab.close()
        html = """<p>dispersion of the fitted data to the model</p>{}<hr>""".format(
        self.create_embedded_png(dispersion, "filename", style=style))
        self.sections.append({
           "name": "4. Dispersion",
           "anchor": "table",
           "content": html
         })

    def add_cluster(self):
        style = "width:65%"
        def dendogram(filename):
            import pylab
            pylab.ioff()
            pylab.clf()
            self.rnadiff.plot_dendogram()
            pylab.savefig(filename)
            pylab.close()
        html_dendogram = """<p>The following image shows a hierarchical
clustering of the whole sample set. An euclidean distance is computed between
samples. The dendogram itself is built using the <a
href="https://en.wikipedia.org/wiki/Ward%27s_method"> Ward method </a>. The data was log-transformed first.
</p>{}<hr>""".format(
        self.create_embedded_png(dendogram, "filename", style=style))

        def pca(filename):
            import pylab
            pylab.ioff()
            pylab.clf()
            variance = self.rnadiff.plot_pca(2)
            pylab.savefig(filename)
            pylab.close()
        html_pca = """<p>The experiment variability is also represented by a
principal component analysis as shown here below. The two main components are
represented. We expect the ﬁrst principal component (PC1) to
separate samples from the diﬀerent biological conditions, meaning that the biological variability is
the main source of variance in the data. Hereafter is also a 3D representation
of the PCA where the first 3 components are shown.

</p>{}<hr>""".format(
            self.create_embedded_png(pca, "filename", style=style))

        from plotly import offline
        fig = self.rnadiff.plot_pca(n_components=3, plotly=True)
        html_pca_plotly = offline.plot(fig, output_type="div",include_plotlyjs=False)

        self.sections.append({
           "name": "2. Clusterisation",
           "anchor": "table",
           "content": html_dendogram + html_pca + html_pca_plotly
         })

    def add_plot_count_per_sample(self):
        style = "width:65%"
        import pylab
        def plotter(filename):
            pylab.ioff()
            pylab.clf()
            self.rnadiff.plot_count_per_sample(rotation=45)
            pylab.savefig(filename)
            pylab.close()
        html1 = """<p>The following image shows the total number of counted reads
for each sample. We expect counts to be similar within conditions. They may be
different across conditions. Note that variation may happen (e.g., different rRNA contamination
levels, library concentrations, etc).<p>{}<hr>""".format(
         self.create_embedded_png(plotter, "filename", style=style))

        def null_counts(filename):
            pylab.ioff()
            pylab.clf()
            self.rnadiff.plot_percentage_null_read_counts()
            pylab.savefig(filename)
            pylab.close()

        html_null = """<p>The next image shows the percentage of features with no
read count in each sample (taken individually). Features with null read counts
in <b>all</b> samples are not
taken into account in the analysis (black dashed line). Fold-change and p-values
will be set to NA in the final results</p> {}<hr>""".format(
            self.create_embedded_png(null_counts, "filename", style=style))

        def count_density(filename):
            pylab.ioff()
            pylab.clf()
            self.rnadiff.plot_density()
            pylab.savefig(filename)
            pylab.close()
        html_density = """<p>In the following figure, we show the distribution
of read counts for each sample (log10 scale). We expect replicates to behave in
a similar fashion. The mode depends on the biological conditions and organism
considered.</p> {}<hr>""".format(
            self.create_embedded_png(count_density, "filename", style=style))

        def best_count(filename):
            pylab.ioff()
            pylab.clf()
            self.rnadiff.plot_feature_most_present()
            pylab.savefig(filename)
            pylab.close()
        html_feature = """<p>The following figure shows for each sample the feature that
capture the highest proportion of the reads considered. This should not impact
the DESeq2 normalization. We expect consistence across samples within a single
condition</p> {}<hr>""".format(
            self.create_embedded_png(best_count, "filename", style=style))


        self.sections.append({
           "name": "1. Diagnostic plots",
           "anchor": "table",
           "content": html1 +  html_null + html_density + html_feature
         })

    def add_normalisation(self):

        style = "width:45%"
        def rawcount(filename):
            import pylab
            pylab.ioff()
            pylab.clf()
            self.rnadiff.plot_boxplot_rawdata()
            ax = pylab.gca()
            xticklabels = ax.get_xticklabels()
            ax.set_xticklabels(xticklabels, rotation=45, ha='right')
            try: pylab.tight_layout()
            except:pass
            pylab.savefig(filename)
            pylab.close()
        def normedcount(filename):
            import pylab
            pylab.ioff()
            pylab.clf()
            self.rnadiff.plot_boxplot_normeddata()
            ax = pylab.gca()
            xticklabels = ax.get_xticklabels()
            ax.set_xticklabels(xticklabels, rotation=45, ha='right')
            try: pylab.tight_layout()
            except:pass
            pylab.savefig(filename)
            pylab.close()
        html_boxplot = """<p>A normalization of the data is performed to correct
the systematic technical biases due to different counts across samples. The 
normalization is performed with DESeq2. It relies on the hypothess that most
features are not differentially expressed. It computes a scaling factor for each
sample. Normalized read counts are obtained by dividing raw read counts by the
scaling factor associated with the sample they belong to.

Boxplots are often used as a qualitative measure of the quality of the normalization process,
as they show how distributions are globally aﬀected during this process. We expect normalization to
stabilize distributions across samples.
The left figure shows the raw counts while the right figure shows the
normalised counts.
</p>"""
        img1 = self.create_embedded_png(rawcount, "filename", style=style)
        img2 = self.create_embedded_png(normedcount, "filename", style=style)


        self.sections.append({
           "name": "3. Normalisation",
           "anchor": "table",
           "content": html_boxplot + img1 + img2 + "</hr>"
         })

    def add_individual_report(self, comp, name, counter):
        style = "width:45%"

        description = """<p>
When the dispersion estimation and model fitting is done, statistical testing is
performed. The distribution of raw p-values computed by the statistical test 
is expected to be a mixture of a uniform distribution on [0, 1] and a peak
around 0 corresponding to the diﬀerentially expressed features. This may not
always be the case. </p>"""

        def plot_pvalue_hist(filename):
            import pylab; pylab.ioff(); pylab.clf()
            comp.plot_pvalue_hist()
            pylab.savefig(filename); pylab.close()

        def plot_padj_hist(filename):
            import pylab; pylab.ioff(); pylab.clf()
            comp.plot_padj_hist()
            pylab.savefig(filename); pylab.close()
        img1 = self.create_embedded_png(plot_pvalue_hist, "filename", style=style)
        img2 = self.create_embedded_png(plot_padj_hist, "filename", style=style)

        # FIXME. pvalues adjusted are not relevant so commented for now
        img2 = ""

        self.sections.append({
           "name": f"6.{counter}.a pvalue distribution ({name})",
           "anchor": f"dge_summary",
           "content": description + img1 + img2 
         })

        def plot_volcano(filename):
            import pylab; pylab.ioff(); pylab.clf()
            comp.plot_volcano()
            pylab.savefig(filename); pylab.close()
        html_volcano = """<p>The volcano plot here below shows the diﬀerentially
expressed features with a adjusted p-value below 0.05 (dashed back line). 
The volcano plot represents the log10 of the adjusted P
value as a function of the log2 ratio of diﬀerential expression. </p>"""
        #img3 = self.create_embedded_png(plot_volcano, "filename", style=style)
        img3=""
        fig = comp.plot_volcano(plotly=True, annotations=self.rnadiff.annotation)
        from plotly import offline
        plotly = offline.plot(fig, output_type="div", include_plotlyjs=False)

        self.sections.append({
           "name": f"6.{counter}.b volcano plots ({name})",
           "anchor": f"{name}_volcano",
           "content":  html_volcano + img3 + "<hr>"  + plotly
         })

        # finally, let us add the tables
        from pylab import log10

        df = comp.df.copy()#.reset_index()

        # here we need to add the annotation if possible
        try:
            df = pd.concat([df, self.rnadiff.annotation.annotation.loc[comp.df.index]], axis=1)
        except Exception as err:
            logger.critical(f"Could not add annotation. {err}")

        df = df.reset_index()

        fold_change = 2**df['log2FoldChange']
        log10padj = -log10(df['padj'])
        df.insert(df.columns.get_loc('log2FoldChange')+1, 'FoldChange', fold_change)
        df.insert(df.columns.get_loc('padj')+1, 'log10_padj', log10padj)

        try:
            del df['dispGeneEst']
            #del df['dispFit']
            #del df['dispMap']
        except:pass

        for x in ['lfcSE', 'stat', 'dispersion']:
            try:del df[x]
            except:pass
        # set options
        options = {'scrollX': 'true',
            'pageLength': 10,
            'scrollCollapse': 'true',
            'dom': 'Bfrtip',
            'buttons': ['copy', 'csv']}

        datatable = DataTable(df, f'{name}_table_all')
        datatable.datatable.datatable_options = options
        js_all = datatable.create_javascript_function()
        html_tab_all = datatable.create_datatable(float_format='%.3e')

        df_sign = df.query("padj<=0.05 and (log2FoldChange>1 or log2FoldChange<-1)")
        datatable = DataTable(df_sign, f'{name}_table_sign')
        datatable.datatable.datatable_options = options
        js_sign = datatable.create_javascript_function()
        html_tab_sign = datatable.create_datatable(float_format='%.3e')

        self.sections.append({
            'name': f"6.{counter}.c {name} Tables ({name})",
            'anchor': f"{name} stats",
            'content':
                f"""<p>The following tables give all DGE results. The
first table contains all significant genes (adjusted p-value below 0.05 and
absolute fold change of at least 0.5). The following tables contains all results
without any filtering. Here is a short explanation for each column:
<ul>
<li> baseMean: base mean over all samples</li>
<li> norm.sampleName: rounded normalized counts per sample</li>
<li> FC: fold change in natural base</li>
<li> log2FoldChange: log2 Fold Change estimated by the model. Reflects change
between the condition versus the reference condition</li>
<li> stat: Wald statistic for the coefficient (contrast) tested</li>
<li> pvalue: raw p-value from statistical test</li>
<li> padj: adjusted pvalue. Used for cutoff at 0.05 </li>
<li> betaConv: convergence of the coefficients of the model </li>
<li> maxCooks: maximum Cook's distance of the feature </li>
<li> outlier: indicates if the feature is an outlier according to Cook's distance
</li>
</ul>
</p>
<h3>Significative only<a id="{name}_table_sign"></a></h3>
here below is a subset of the next table. It contains all genes below adjusted
p-value of 0.05 and absolute log2 fold change above 1.
{js_sign} {html_tab_sign} 

<h3>All genes<a id="{name}_table_all"></a></h3>
{js_all} {html_tab_all}"""
        })
