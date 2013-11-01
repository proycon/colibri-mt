#!/usr/bin/env python3

import colibricore


class FeaturePhraseTable:
    def __init__(self, sourcedecoder, targetdecoder):
        self.classifiers = [] #list of all classifierdata, list consists of two tuple (features, targetpattern)
        self.sourcepatterns = colibricore.PatternDict_int32()

    def add(self, sourcepattern, features, targetpattern):
        if not isinstance(sourcepattern, colibricore.Pattern):
            raise ValueError("Source pattern must be instance of Pattern")
        if not isinstance(targetpattern, colibricore.Pattern):
            raise ValueError("Target pattern must be instance of Pattern")

        if sourcepattern in self.sourcepatterns:
            classifierid = self.sourcepatterns[sourcepattern]
        else:
            self.classifiers.append( [(features, targetpattern) ] )
            classifierid = len(self.classifiers)

    def __len__(self):
        return len(self.sourcepatterns)

    def __iter__(self):
        for sourcepattern, classifierid in self.sourcepatterns:
            for features, targetpattern in self.classifiers[classifierid]:
                yield sourcepattern, features, targetpattern

    def __getitem__(self, sourcepattern):
        return self.classifiers[self.sourcepatterns[sourcepattern]]

    def loadmoses(self, filename, sourceencoder, targetencoder):
        pass #TODO

    def load(self, filename, sourceencoder, targetencoder):
        pass #TODO

    def save(self, filename):
        """Output"""
        pass #TODO

    def savemoses(self, filename):
        """Output for moses"""
        pass #TODO









