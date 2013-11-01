#!/usr/bin/env python3

import colibricore


class FeaturePhraseTable:
    def __init__(self, sourcedecoder, targetdecoder):
        self.classifiers = [] #list of all classifierdata, list consists of two tuple (features, targetpattern)
        self.sourcepatterns = colibricore.PatternDict_int32()
        self.sourcedecoder = sourcedecoder
        self.targetdecoder = targetdecoder

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
        with open(filename,'r',encoding='utf-8') as f:
            for line in f:
                fields = line.strip().split("\t")
                sourcepattern = sourceencoder.buildpattern(fields[0])
                targetpattern = targetencoder.buildpattern(fields[-1])
                for raw in fields[1:-1]:
                    type, value = fields.split('=',2)
                    features = []
                    if type == 's':
                        features.append(value)
                    elif type == 'p':
                        features.append(sourceencoder.buildpattern(value))
                    elif type == 'i':
                        features.append(int(value))
                    elif type == 'f':
                        features.append(float(value))
                    elif type == 'b':
                        features.append(bool(value))
                self.add(sourcepattern,features,targetpattern)

    def save(self, filename):
        """Output"""
        with open(filename,'w',encoding='utf-8') as f:
            for sourcepattern, features, targetpattern in self:
                f.write(sourcepattern.tostring(self.sourcedecoder))
                for feature in features:
                    f.write("\t")
                    if isinstance(feature,str):
                        f.write('s=' + feature)
                    elif isinstance(feature, colibricore.Pattern):
                        f.write('p=' + feature.tostring(self.sourcedecoder))
                    elif isinstance(feature,int):
                        f.write('i=' + str(feature))
                    elif isinstance(feature,float):
                        f.write('f=' + str(feature))
                    elif isinstance(feature,bool):
                        f.write('b=' + str(feature))
                    else:
                        raise TypeError
                f.write("\t" + targetpattern.tostring(self.targetdecoder)+"\n")


    def savemoses(self, filename):
        """Output for moses"""
        pass #TODO









