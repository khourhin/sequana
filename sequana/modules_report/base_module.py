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
"""Generic module is the parent module of all other module"""
import os
import shutil
import jinja2
import io
import base64

from reports import HTMLTable
from sequana.utils import config


class SequanaBaseModule(object):
    """ Generic Module to write HTML reports.
    """
    required_dir = ("css", "js", "images")
    def __init__(self):
        self.output_dir = config.output_dir
        self.path = "./"
        # Initiate jinja template
        template = config.template_dict[config.template].load()
        env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(template.template_dir))
        self.j_template = env.get_template(template.base_fn)
        self._init_report()

    def _init_report(self):
        """ Create the report directory.
        """
        # Create report directory
        if os.path.isdir(config.output_dir) is False:
            os.mkdir(self.output_dir)
        for directory in self.required_dir:
            complete_directory = os.sep.join([self.output_dir, directory])
            if os.path.isdir(complete_directory) is False:
                os.mkdir(complete_directory)

        # Copy css/js necessary files
        for filename in config.css_list:
            target = os.sep.join([self.output_dir, 'css'])
            if os.path.isfile(target) is False:
                shutil.copy(filename, target)
        for filename in config.js_list:
            target = os.sep.join([self.output_dir, 'js'])
            if os.path.isfile(target) is False:
                shutil.copy(filename, target)

    def create_html(self, output_filename):
        """ Create html with Jinja2.
        """
        report_output = self.j_template.render(config=config,
                                               module=self)
        with open(os.sep.join([config.output_dir,output_filename]),
                  "w") as fp:
            print(report_output, file=fp)

    def create_link(self, name, target):
        """ Create an html link with name and target.
        """
        return '<a href="{0}" download="{0}">{1}</a>'.format(target, name)

    def create_hide_section(self, name, link, content):
        """ Create an hideable section.
        """
        link = "<a href='#1' class='show_hide{0}'>{1}</a>".format(name, link)
        content = "<div class='slidingDiv{0}'>\n{2}\n</div>".format(name,
                                                                    content)
        return link, content

    def copy_file(self, filename, target_dir):
        """ Copy a file to a target directory. Return the relative path of your
        file.
        """
        try:
            os.makedirs(target_dir)
        except FileExistsError:
            if os.path.isdir(target_dir):
                pass
            else:
                msg = "{0} exist and it is not a directory".format(target_dir)
                config.logger.error(msg)
                raise FileExistsError
        try:
            shutil.copy(filename, target_dir)
        except FileNotFoundError:
            msg = "{0} doesn't exist".format(filename)
            raise FileNotFoundError 
        return target_dir + os.sep + os.path.basename(filename)

    def add_float_right(self, content):
        """ Add content align to right.
        """
        return '<div style="float:right">{0}</div>'.format(content)

    def add_code_section(self, content, language):
        """ Add code in your html.
        """
        html = '<pre><code class="{0}">{1}</code></pre>'
        return html.format(language, content)

    def dataframe_to_html_table(self, dataframe, kwargs=dict()):
        """ Convert dataframe in html.
        """
        html = HTMLTable(dataframe)
        return html.to_html(**kwargs)

    def include_svg_image(self, filename):
        """ Include SVG image in the html.
        """
        html = ('<object data="{0}" type="image/svg+xml">\n'
                '<img src="{0}"></object>')
        return html.format(filename)

    def png_to_embedded_png(self, png, style=None):
        """ Include a PNG file as embedded file.
        """
        with open(png, 'rb') as fp:
            png = fp.read().encode('base64').replace('\n','')
        if style:
            html = '<img style="{0}"'.format(style)
        else:
            html = "<img "
        return '{0} src="data:image/png;base64,{1}">'.format(html, png)

    def create_embedded_png(self, plot_function, input_arg, kwargs=dict(),
                            style=None):
        """ Take as a plot function as input and create a html embedded png
        image. You must set the arguments name for the output to connect
        buffer.
        """
        buf = io.BytesIO()
        # add buffer as output of the plot function
        kwargs = dict({input_arg: buf}, **kwargs)
        plot_function(**kwargs)
        if style:
            html = '<img style="{0}" '.format(style)
        else:
            html = '<img '
        html += 'src="data:image/png;base64,{0}"/>'.format(
            base64.b64encode(buf.getvalue()).decode('utf-8'))
        buf.close()
        return html
