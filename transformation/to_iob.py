"""
This script serves to transform the custom XML format to iob-formatted files.
Requirements:
- It should be possible to create multiple columns for different tags (such as full span and head span)
- It should be possible for each column to define what kind of tag should be written in there

Concrete examples that should be possible to be created:
- Get all full span tags but only their entity_class
- Get all head span tags with mention_class + entity_class
- Get all head span tags which are Named Entity Mentions.
"""

