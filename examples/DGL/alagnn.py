#!/usr/bin/env python
# coding: utf-8
import random
import math
import torch
import dgl
import graphgallery
from graphgallery.datasets import Planetoid

print("GraphGallery version: ", graphgallery.__version__)
print("PyTorch version: ", torch.__version__)
print("DGL version: ", dgl.__version__)

'''
Load Datasets
- cora/citeseer/pubmed
'''
data = Planetoid('cora', root="~/GraphData/datasets/", verbose=False)
graph = data.graph
device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
# splits = data.split_nodes()
graphgallery.set_backend("dgl")

# experimental setup in
# `When Do GNNs Work: Understanding and Improving Neighborhood Aggregation
# <https://www.ijcai.org/Proceedings/2020/0181.pdf>`
random.seed(2020)
split = 0.01
n_nodes = graph.num_nodes
sample_size = math.ceil(n_nodes * split)
train_idx = random.sample(range(n_nodes - 1000), sample_size)
train_nodes = [idx if idx < 500 else idx + 1000 for idx in train_idx]
test_nodes = list(range(500, 1500))


from graphgallery.gallery.nodeclas import ALaGCN, ALaGAT
# trainer = ALaGAT(device=device, seed=123).setup_graph(graph).build()
trainer = ALaGCN(device=device, seed=123).setup_graph(graph).build()
trainer.fit(train_nodes, verbose=1)
results = trainer.evaluate(test_nodes)
print(f'Test loss {results.loss:.5}, Test accuracy {results.accuracy:.2%}')
