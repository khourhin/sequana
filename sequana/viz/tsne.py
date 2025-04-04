# -*- coding: utf-8 -*-
#
#  This file is part of Sequana software
#
#  Copyright (c) 2016-2020 - Sequana Development Team
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

import colorlog

from sequana.lazy import pylab

logger = colorlog.getLogger(__name__)

from sequana.viz import clusterisation

__all__ = ["TSNE"]


class TSNE(clusterisation.Cluster):
    """

    .. plot::
        :include-source:

        from sequana.viz.tsne import TSNE
        from sequana import sequana_data
        import pandas as pd

        data = sequana_data("test_pca.csv")
        df = pd.read_csv(data)
        df = df.set_index("Id")
        p = TSNE(df, colors={
            "A1": 'r', "A2": 'r', 'A3': 'r',
            "B1": 'b', "B2": 'b', 'B3': 'b'})
        p.plot(perplixity=2)

    """

    def __init__(self, data, colors={}):
        super(TSNE, self).__init__(data, colors)

    def plot(
        self,
        n_components=2,
        perplexity=30,
        n_iter=1000,
        init="random",
        random_state=0,
        transform="log",
        switch_x=False,
        switch_y=False,
        switch_z=False,
        colors=None,
        max_features=500,
        show_plot=True,
        show_labels=False,
    ):
        """

        :param n_components: at number starting at 2 or a value below 1
            e.g. 0.95 means select automatically the number of components to
            capture 95% of the variance
        :param transform: can be 'log' or 'anscombe', log is just log10. count
            with zeros, are set to 1
        """
        import numpy as np
        from sklearn.manifold import TSNE

        pylab.clf()

        data = self.scale_data(transform_method=transform)

        # keep only top variable features
        tokeep = data.std(axis=1).sort_values(ascending=False).index[0:max_features]
        data = data.loc[tokeep]

        tsne = TSNE(
            perplexity=perplexity, n_components=n_components, max_iter=n_iter, random_state=random_state, init=init
        )
        Xr = tsne.fit_transform(data.T)
        self.Xr = Xr

        if switch_x:
            Xr[:, 0] *= -1
        if switch_y:
            Xr[:, 1] *= -1
        if switch_z:
            Xr[:, 2] *= -1

        # PC1 vs PC2
        if show_plot:
            pylab.figure(1)
            self._plot(Xr, pca=None, pc1=0, pc2=1, colors=colors, show_labels=show_labels)

        if n_components >= 3:
            if show_plot:
                pylab.figure(2)
                self._plot(Xr, pca=None, pc1=0, pc2=2, colors=colors, show_labels=show_labels)
                pylab.figure(3)
                self._plot(Xr, pca=None, pc1=1, pc2=2, colors=colors, show_labels=show_labels)
        return tsne
