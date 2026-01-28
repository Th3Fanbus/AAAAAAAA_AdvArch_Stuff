# Spark Assignment

## Assignment Directions

A logistics company wants to compute the minimal road distance between
cities in its network. The road network is modeled as a weighted
directed graph:

- Each vertex is a city (defined by an integer ID).
- Each edge is a road with a distance (positive weight).

You will use Apache Spark RDDs to implement an iterative shortest-path
algorithm (a Dijkstra-style relaxation) to compute the minimal distance
from a source city to all other cities. In the [sample notebook] you
will find a possible idea.

[sample notebook]: https://github.com/wisaaco/AA_DistributedSystems_Lab/blob/main/U9-Spark/spark_activity.ipynb

## Random Thoughts

Huh, the directions say to use integer IDs for vertices, but the sample
notebook uses strings. I guess it doesn't matter as long as it works.
