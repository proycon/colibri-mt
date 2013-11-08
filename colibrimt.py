#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import datetime
import bz2
import gzip
import colibricore
import timbl
import argparse
import pickle



class AlignmentModel:
    def __init__(self, multivalue=True, singleintvalue=False):
        self.values = []
        self.newvalueid = 0
        self.alignedpatterns = colibricore.AlignedPatternDict_int32()
        self.sourcedecoder = sourcedecoder
        self.targetdecoder = targetdecoder
        self.multivalue = multivalue
        self.singleintvalue = singleintvalue

    def add(self, sourcepattern, targetpattern, value):
        if not isinstance(sourcepattern, colibricore.Pattern):
            raise ValueError("Source pattern must be instance of Pattern")
        if not isinstance(targetpattern, colibricore.Pattern):
            raise ValueError("Target pattern must be instance of Pattern")

        if (sourcepattern, targetpattern) in self.alignedpatterns:
            valueid = self.alignedpatterns[(sourcepattern, targetpattern)]
            if self.singleintvalue:
                self.alignedpatterns[(sourcepattern,targetpattern)] = value
            elif self.multivalue:
                self.values[valueid].append(value)
            else:
                self.values[valueid] = value
        else:
            self.newvalueid += 1
            valueid = self.newvalueid
            if self.singleintvalue:
                self.alignedpatterns[(sourcepattern,targetpattern)] = value
            elif self.multivalue:
                self.values[valueid] = [value]
            else:
                self.values[valueid] = value

    def __len__(self):
        return len(self.alignedpatterns)

    def __iter__(self):
        if self.singleintvalue:
            for sourcepattern, targetpattern, value in self.alignedpatterns.items():
                yield sourcepattern, targetpattern, value
        else:
            for sourcepattern, targetpattern, valueid in self.alignedpatterns.items():
                yield sourcepattern, targetpattern, self.values[valueid]

    def sourcepatterns(self):
        for sourcepattern in self.alignedpatterns:
            yield sourcepattern


    def targetpatterns(self, sourcepattern):
        for targetpattern in self.alignedpatterns.children(sourcepattern):
            yield targetpattern

    def items(self):
        return iter(self)

    def __getitem__(self, item):
        if self.singleintvalue:
            return self.alignedpatterns[item]
        else:
            return self.values[self.alignedpatterns[item]]

    def __setitem__(self, item, value):
        if self.singleintvalue:
            self.alignedpatterns[item] = value
        else:
            self.values[self.alignedpatterns[item]] = value


    def __contains__(self, item):
        return item in self.alignedpatterns


    def load(self, fileprefix):
        self.alignedpatterns.read(fileprefix + ".colibri.alignmodel-keys")
        self.values = pickle.load(fileprefix + ".colibri.alignmodel-values")

    def save(self, fileprefix):
        """Output"""
        self.alignedpatterns.write(fileprefix + ".colibri.alignmodel-keys")
        pickle.dump(self.values, fileprefix + ".colibri.alignmodel-values")



class FeaturedAlignmentModel(AlignmentModel):
    def __init__(self, conf):
        assert isinstance(conf, FeatureConfiguration)
        self.conf = conf
        super().__init__(True,False)


    def savemoses(self, filename, sourcedecoder, targetdecoder):
        """Output for moses"""
        with open(filename,'w',encoding='utf-8') as f:
            for sourcepattern, targetpattern, features in self:
                f.write(sourcepattern.tostring(sourcedecoder) + " ||| " + targetpattern.tostring(targetdecoder) + " ||| ")
                for i, feature, featureconf in enumerate(zip(features, self.conf)):
                    if featureconf[0] != Pattern and featureconf[1]:
                        if (i > 0): f.write(" ")
                        f.write(str(feature))
                f.write("\n")

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


            self.add(source,target, scores)

        f.close()

        self.conf = FeatureConfiguration()
        for x in scores:
            self.conf.addscorefeature(float)



    def extractfeatures(self, featureconf, sourcemodel, targetmodel, factoredcorpora):
        """Extracts features and adds it to the phrasetable"""

        #factoredcorpora is a list of IndexedCorpus instances, for each of the factors.. the base data is considered a factor like any other



        if len(factoredcorpora) != len(featureconf):
            raise ValueError("Expected " + str(len(featureconf)) + " instances in factoredcorpora, got " + str(len(factoredcorpora)))

        if not all([ isinstance(x,colibricore.IndexedCorpus) for x in factoredcorpora]):
            raise ValueError("factoredcorpora elements must be instances of IndexedCorpus")

        assert isinstance(sourcemodel, colibricore.IndexedPatternModel)
        assert isinstance(targetmodel, colibricore.IndexedPatternModel)

        for pattern in self.sourcepatterns:
            if not pattern in sourcemodel:
                print("Warning: a pattern from the phrase table was not found in the source model (pruned for not meeting a threshold most likely)" ,file=sys.stderr)
                continue


            sourceindexes = sourcemodel[pattern]

            for features, targetpattern in self[pattern]:
                if not targetpattern in targetmodel:
                    print("Warning: a pattern from the phrase table was not found in the target model (pruned for not meeting a threshold most likely)" ,file=sys.stderr)
                    continue

                targetindexes = targetmodel[targetpattern]

                #for every occurrence of this pattern in the source
                for sentence, token in sourceindexes:

                    #is a target pattern found in the same sentence? (if so we *assume* they're aligned, we don't actually use the word alignments anymore here)
                    targetmatch = False
                    for targetsentence,_ in targetindexes:
                        if sentence == targetsentence:
                            targetmatch = True
                            break
                    if not targetmatch:
                        continue

                    #good, we can start extracting features!!

                    #add the location to the features so we can find it later when we build intermediate location-based IDs instead of sourcepatterns
                    features.append(sentence)
                    features.append(token)

                    for factoredcorpus, factor in zip(factoredcorpora, featureconf.factors):
                        classdecoder, leftcontext, rightcontext = factor
                        features += _extractfeatures(pattern, sentence, token, factoredcorpus, leftcontext, rightcontext)





def _extractfeatures(pattern, sentence, token, factoredcorpus, leftcontext, rightcontext):
    featurevector = []
    n = len(pattern)
    sentencelength = factoredcorpus.sentencelength(sentence)
    for i in range(token - leftcontext,token):
        if token < 0:
            unigram = colibricore.BEGINPATTERN
        else:
            unigram = factoredcorpus[(sentence,i)]
        featurevector.append(unigram)
    for i in range(token + n , token + n + rightcontext):
        if token > sentencelength:
            unigram = colibricore.ENDPATTERN
        else:
            unigram = factoredcorpus[(sentence,i)]
        featurevector.append(unigram)
    return featurevector

class FeatureConfiguration:


    #the feature vectors will contain:
    #   the two-tuple (sentence, tokenoffset) of the beginning occurrence
    #   leftcontext from sourcepatternmodel
    #   rightcontext from sourcepatternmodel
    #   for each of the factors:
    #       leftcontext from factored indexedcorpus
    #        rightcontext from factored indexedcorpus


    def __init__(self):
        self.conf = []

    def addfactorfeature(self, classdecoder, leftcontext=0, rightcontext=0):
        self.conf.append( ( Pattern, classdecoder, leftcontext, rightcontext) )

    def addfeature(self, type):
        """Will not be propagated to Moses phrasetable"""
        self.conf.append( ( type,False) )

    def addscorefeature(self, type):
        """Will be propagated to Moses phrasetable"""
        self.conf.append( ( type,True) )

    def __len__(self):
        return len(self.conf)

    def __iter__(self):
        for x in self.conf:
            yield x

    def __getitem__(self, index):
        return self.conf[index]


