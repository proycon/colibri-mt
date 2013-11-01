#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import colibricore
import sys
import datetime
import bz2
import gzip


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


    def load(self, filename, sourceencoder, targetencoder):
        with open(filename,'r',encoding='utf-8') as f:
            for line in f:
                fields = line.strip().split("\t")
                sourcepattern = sourceencoder.buildpattern(fields[0])
                targetpattern = targetencoder.buildpattern(fields[-1])
                for raw in fields[1:-1]:
                    type, value = raw.split('=',2)
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


    def loadmoses(self, filename, sourceencoder, targetencoder, quiet=False, reverse=False, delimiter="|||", score_column = 3, max_sourcen = 0, scorefilter = lambda x:True):
        """Load a phrase table from file into memory (memory intensive!)"""
        self.phrasetable = {}

        if filename.split(".")[-1] == "bz2":
            f = bz2.BZ2File(filename,'r')
        elif filename.split(".")[-1] == "gz":
            f = gzip.GzipFile(filename,'r')
        else:
            f = open(filename,'r',encoding='utf-8')
        linenum = 0
        prevsource = None
        targets = []

        while True:
            if not quiet:
                linenum += 1
                if (linenum % 100000) == 0:
                    print("Loading phrase-table: @" + str(linenum) + "\t(" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ")",file=sys.stderr)
            line = f.readline()
            if not line:
                break

            #split into (trimmed) segments
            segments = [ segment.strip() for segment in line.split(delimiter) ]

            if len(segments) < 3:
                print("Invalid line: ", line, file=sys.stderr)
                continue

            #Do we have a score associated?
            if score_column > 0 and len(segments) >= score_column:
                scores = tuple( ( float(x) for x in segments[score_column-1].strip().split() ) )
            else:
                scores = tuple()

            #if align2_column > 0:
            #    try:
            #        null_alignments = segments[align2_column].count("()")
            #    except:
            #        null_alignments = 0
            #else:
            #    null_alignments = 0

            if scorefilter:
                if not scorefilter(scores): continue

            if reverse:
                if max_sourcen > 0 and segments[1].count(' ') + 1 > max_sourcen:
                    continue

                source = sourceencoder.buildpattern(segments[1]) #tuple(segments[1].split(" "))
                target = targetencoder.buildpattern(segments[0]) #tuple(segments[0].split(" "))
            else:
                if max_sourcen > 0 and segments[0].count(' ') + 1 > max_sourcen:
                    continue

                source = sourceencoder.buildpattern(segments[0]) #tuple(segments[0].split(" "))
                target = targetencoder.buildpattern(segments[1]) #tuple(segments[1].split(" "))


            self.add(source, scores, target)

        f.close()







