import numpy as np
from graphgallery.data.sequence import MiniBatchSequence
from graphgallery.gallery import Trainer
from graphgallery.nn.models import get_model
from graphgallery import functional as gf
from graphgallery.gallery.nodeclas import TensorFlow


@TensorFlow.register()
class ClusterGCN(Trainer):
    """
        Implementation of Cluster Graph Convolutional Networks (ClusterGCN).

        `Cluster-GCN: An Efficient Algorithm for Training Deep and Large Graph Convolutional Networks
        <https://arxiv.org/abs/1905.07953>`
        Tensorflow 1.x implementation: 
        <https://github.com/google-research/google-research/tree/master/cluster_gcn>
        Pytorch implementation: 
        <https://github.com/benedekrozemberczki/ClusterGCN>

    """

    def data_step(self,
                  adj_transform="normalize_adj",
                  attr_transform=None,
                  num_clusters=10,
                  partition='metis'):

        graph = self.graph
        batch_adj, batch_x, cluster_member = gf.graph_partition(
            graph, num_clusters=num_clusters, partition=partition)

        batch_adj = gf.get(adj_transform)(*batch_adj)
        batch_x = gf.get(attr_transform)(*batch_x)

        batch_adj, batch_x = gf.astensors(batch_adj, batch_x, device=self.data_device)

        # ``A`` and ``X`` and ``cluster_member`` are cached for later use
        self.register_cache(batch_x=batch_x, batch_adj=batch_adj,
                            cluster_member=cluster_member)
        # for louvain clustering
        self.cfg.data.num_clusters = len(cluster_member)

    def model_step(self,
                   hids=[32],
                   acts=['relu'],
                   dropout=0.5,
                   weight_decay=0.,
                   lr=0.01,
                   bias=False):
        # FIXME:
        # WARNING:tensorflow:5 out of the last 104 calls to <bound method TFEngine.test_step_on_batch of <graphgallery.nn.models.tensorflow.gcn.GCN object at 0x000001FCA2373808>> triggered tf.function retracing. Tracing is expensive and the excessive number of tracings could be due to (1) creating @tf.function repeatedly in a loop, (2) passing tensors with different shapes, (3) passing Python objects instead of tensors. For (1), please define your @tf.function outside of the loop. For (2), @tf.function has experimental_relax_shapes=True option that relaxes argument shapes that can avoid unnecessary retracing. For (3), please refer to https://www.tensorflow.org/guide/function#controlling_retracing and https://www.tensorflow.org/api_docs/python/tf/function for  more details.

        model = get_model("GCN", self.backend)
        model = model(self.graph.num_node_attrs,
                      self.graph.num_node_classes,
                      hids=hids,
                      acts=acts,
                      dropout=dropout,
                      weight_decay=weight_decay,
                      lr=lr,
                      bias=bias,
                      experimental_run_tf_function=False)

        # if LooseVersion(tf.__version__) < LooseVersion("2.2.0") and use_tfn:
        #     model.use_tfn()

        return model

    def train_loader(self, index):
        node_mask = gf.index_to_mask(index, self.graph.num_nodes)
        labels = self.graph.label
        cache = self.cache

        batch_mask, batch_y = [], []
        batch_x, batch_adj = [], []
        for cluster in range(self.cfg.data.num_clusters):
            nodes = cache.cluster_member[cluster]
            mask = node_mask[nodes]
            y = labels[nodes][mask]
            if y.size == 0:
                continue
            batch_x.append(cache.batch_x[cluster])
            batch_adj.append(cache.batch_adj[cluster])
            batch_mask.append(mask)
            batch_y.append(y)

        batch_inputs = tuple(zip(batch_x, batch_adj))
        sequence = MiniBatchSequence(inputs=batch_inputs,
                                     y=batch_y,
                                     out_index=batch_mask,
                                     device=self.data_device)
        return sequence

    def predict(self, index):
        cache = self.cache

        node_mask = gf.index_to_mask(index, self.graph.num_nodes)
        orders_dict = {idx: order for order, idx in enumerate(index)}
        batch_mask, orders = [], []
        batch_x, batch_adj = [], []
        for cluster in range(self.cfg.data.num_clusters):
            nodes = cache.cluster_member[cluster]
            mask = node_mask[nodes]
            batch_nodes = np.asarray(nodes)[mask]
            if batch_nodes.size == 0:
                continue
            batch_x.append(cache.batch_x[cluster])
            batch_adj.append(cache.batch_adj[cluster])
            batch_mask.append(mask)
            orders.append([orders_dict[n] for n in batch_nodes])

        batch_data = tuple(zip(batch_x, batch_adj))

        logit = np.zeros((index.size, self.graph.num_node_classes),
                         dtype=self.floatx)
        batch_data, batch_mask = gf.astensors(batch_data, batch_mask, device=self.data_device)

        model = self.model
        for order, inputs, mask in zip(orders, batch_data, batch_mask):
            output = model.predict_step_on_batch(inputs, out_index=mask)
            logit[order] = output

        return logit
