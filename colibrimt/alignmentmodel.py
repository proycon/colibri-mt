#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import datetime
import bz2
import gzip
import colibricore
import argparse
import pickle
import os
from collections import defaultdict
from urllib.parse import quote_plus, unquote_plus


class AlignmentModel:
    def __init__(self, multivalue=True, singleintvalue=False):
        self.values = {}
        self.newvalueid = 0
        self.alignedpatterns = colibricore.AlignedPatternDict_int32()
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
                self.alignedpatterns[(sourcepattern,targetpattern)] = valueid
                self.values[valueid] = [value]
            else:
                self.alignedpatterns[(sourcepattern,targetpattern)] = valueid
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


    def targetpatterns(self, sourcepattern=None):
        if sourcepattern is None:
            s = colibricore.PatternSet() #//segfaults (after 130000+ entries)? can't figure out why yet
            #s = set()
            for sp in self.alignedpatterns:
                for targetpattern in self.alignedpatterns.children(sp):
                    s.add(targetpattern)

            for targetpattern in s:
                yield targetpattern
        else:
            for targetpattern in self.alignedpatterns.children(sourcepattern):
                yield targetpattern

    def items(self):
        return iter(self)

    def itemcount(self):
        count = 0
        for _ in self.items():
            count += 1
        return count

    def __getitem__(self, item):
        if self.singleintvalue:
            return self.alignedpatterns[item]
        else:
            return self.values[self.alignedpatterns[item]]

    def __setitem__(self, item, value):
        if self.singleintvalue:
            self.alignedpatterns[item] = value
        else:
            if not item in self.alignedpatterns:
                self.newvalueid +=1
                self.alignedpatterns[item] = self.newvalueid
            self.values[self.alignedpatterns[item]] = value


    def __contains__(self, item):
        return item in self.alignedpatterns

    def haspair(self, sourcepattern, targetpattern):
        return self.alignedpatterns.haspair(sourcepattern, targetpattern)

    def load(self, fileprefix):
        if not os.path.exists(fileprefix + ".colibri.alignmodel-keys"):
            raise IOError("File not found: " + fileprefix + ".colibri.alignmodel-keys")
        self.alignedpatterns.read(fileprefix + ".colibri.alignmodel-keys")
        print( "Loaded keys: alignments for " + str(len(self.alignedpatterns)) + " source patterns",file=sys.stderr)
        if os.path.exists(fileprefix + ".colibri.alignmodel-values"):
            self.singleintvalue= False
            with open(fileprefix + ".colibri.alignmodel-values",'rb') as f:
                self.values = pickle.load(f)
            #check if we are multivalued
            for key, value in self.values.items():
                self.multivalue = (isinstance(value, tuple) or isinstance(value, list))
                break
            print( "Loaded values (" + str(len(self.values)) + ")",file=sys.stderr)
        else:
            self.singleintvalue= True

    def save(self, fileprefix):
        """Output"""
        self.alignedpatterns.write(fileprefix + ".colibri.alignmodel-keys")
        if not self.singleintvalue:
            with open(fileprefix + ".colibri.alignmodel-values",'wb') as f:
                pickle.dump(self.values, f)

    def output(self, sourcedecoder, targetdecoder, scorefilter=None):
        for sourcepattern, targetpattern, value in self.items():
            if scorefilter and not scorefilter(value): continue
            print(sourcepattern.tostring(sourcedecoder) + "\t" ,end="")
            print(targetpattern.tostring(targetdecoder) + "\t" ,end="")
            if not self.multivalue or self.singleintvalue:
                print(str(value))
            else:
                for v in value:
                    print(str(v) + "\t" ,end="")
            print()



    def sourcemodel(self):
        model = colibricore.UnindexedPatternModel()
        for sourcepattern in self.sourcepatterns():
            model[sourcepattern] = model[sourcepattern] + 1
        return model

    def targetmodel(self):
        model = colibricore.UnindexedPatternModel()
        for targetpattern in self.targetpatterns():
            model[targetpattern] = model[targetpattern] + 1
        return model

    def _normaux(self, sourcepattern, targetpattern, total_s, total_t, value, index, sumover):
        if sumover == 's':
            total_s[sourcepattern] += value[index]
        elif sumover == 't':
            total_t[targetpattern] += value[index]
        else:
            raise Exception("sumover can't be " + sumover)


class FeatureConfiguration:
    def __init__(self):
        self.conf = []
        self.decoders = {}

    def addcontextfeature(self, classdecoder, leftcontext=0, focus=True,rightcontext=0):
        if isinstance(classdecoder, colibricore.ClassDecoder):
            self.decoders[classdecoder.filename] = classdecoder
            classdecoder = classdecoder.filename
        elif not isinstance(classdecoder,str):
            raise ValueError
        self.conf.append( ( colibricore.Pattern, classdecoder, leftcontext, focus, rightcontext) )

    def addfeature(self, type, score=False, classifier=False):
        self.conf.append( ( type,score,classifier) )

    def __getstate__(self):
        result = self.__dict__.copy()
        del result['decoders']
        return result

    def __setstate__(self,state):
        self.__dict__ = state
        #after unpickling
        self.decoders = {}

    def __len__(self):
        count = 0
        for x in self.conf:
            if x[0] is colibricore.Pattern:
                count += x[2] + x[4]
                if x[3]:
                    count += 1
            else:
                count += 1
        return count

    def __iter__(self):
        for x in self.conf:
            yield x

    def items(self, forscore=True,forclassifier=True,forall=True,select=None):
        if select:
            if len(select) != len(self):
                raise Exception("Select arguments has length ",len(select), ", expected " , len(self))

        i = 0
        for x in self.conf:
            if forall:
                if select:
                    yield x, select[i]
                else:
                    yield x
            elif x[0] is colibricore.Pattern and forclassifier:
                if select:
                    count = x[2] + x[4]
                    if x[3]: count += 1
                    yield x, select[i:i+count]
                    i = (i+count)-1
                else:
                    yield x
            elif (x[1] and forscore) or (len(x) == 3 and x[2] and forclassifier): #length check necessary for backwards compatibility
                if select:
                    yield x, select[i]
                else:
                    yield x

            i+=1

    def scorefeatures(self, select=None):
        for x in self.items(True,False,False,select):
            yield x

    def classifierfeatures(self, select=None):
        for x in self.items(False,True,False,select):
            yield x


    def __getitem__(self, index):
        return self.conf[index]


    def __setitem__(self, index, value):
        self.conf[index] = value

    def loaddecoders(self, *args):
        for item in self:
            if item[0] == colibricore.Pattern:
                decoderfile = item[1]
                if decoderfile not in self.decoders:
                    foundinargs = False
                    for x in args:
                        if x.filename == decoderfile:
                            print("Linking decoder " + x.filename,file=sys.stderr)
                            self.decoders[x.filename] = x
                            foundinargs = True
                            break
                    if not foundinargs:
                        print("Loading decoder " + decoderfile,file=sys.stderr)
                        self.decoders[decoderfile] = colibricore.ClassDecoder(decoderfile)


class FeaturedAlignmentModel(AlignmentModel):
    def __init__(self, conf=FeatureConfiguration()):
        assert isinstance(conf, FeatureConfiguration)
        self.conf = conf
        super().__init__(True,False)


    def load(self, fileprefix):
        if os.path.exists(fileprefix + ".colibri.alignmodel-featconf"):
            with open(fileprefix + ".colibri.alignmodel-featconf",'rb') as f:
                self.conf.conf = pickle.load(f)
            super().load(fileprefix)
        else:
            raise IOError("File not found: " + fileprefix + ".colibri.alignmodel-featconf")

    def save(self, fileprefix):
        with open(fileprefix + ".colibri.alignmodel-featconf",'wb') as f:
            pickle.dump(self.conf.conf, f)
        super().save(fileprefix)

    def __iter__(self):
        for sourcepattern, targetpattern, valueid in self.alignedpatterns.items():
            for featurevector in self.values[valueid]: #multiple feature vectors per alignment possible
                yield sourcepattern, targetpattern, featurevector

    def output(self, sourcedecoder, targetdecoder, scorefilter=None, *preloadeddecoders):
        if preloadeddecoders:
            preloadeddecoders = (sourcedecoder, targetdecoder) +  preloadeddecoders
        else:
            preloadeddecoders = (sourcedecoder, targetdecoder)
        self.conf.loaddecoders(*preloadeddecoders)

        print("Configuration:",len(self.conf),file=sys.stderr)

        for sourcepattern, targetpattern, features in self.items():
            if scorefilter and not scorefilter(features): continue
            print(self.itemtostring(sourcepattern, targetpattern, features,sourcedecoder, targetdecoder))

    def itemtostring(self, sourcepattern,targetpattern, features, sourcedecoder, targetdecoder, forscore=True,forclassifier=True,forall=True, conf=None):
        if not conf: conf = self.conf
        s = []
        if not forclassifier:
            s.append( sourcepattern.tostring(sourcedecoder) )
            s.append( targetpattern.tostring(targetdecoder) )
        if len(features) < len(conf):
            print(repr(conf.conf),file=sys.stderr)
            print(repr(features),file=sys.stderr)
            raise Exception("Expected " + str(len(conf)) + " features, got " + str(len(features)))

        for i, (currentconf, feature) in enumerate(conf.items(forscore,forclassifier,forall, features) ):
            if currentconf[0] == colibricore.Pattern:
                _, classdecoder, leftcontext, dofocus, rightcontext = currentconf
                classdecoder = self.conf.decoders[classdecoder]
                n = leftcontext + rightcontext
                if dofocus: n += 1
                for j in range(0,n):
                    p = feature[j]
                    if not isinstance(p,  colibricore.Pattern):
                        raise Exception("Feature configuration ",(i,j), ": Expected Pattern, got ",str(type(p)))
                    feature_s = p.tostring(classdecoder)
                    if not feature_s:
                        print("Feature: " + str(repr(bytes(p))) ,file=sys.stderr)
                        print("Feature vector thus far: " + str(repr(s)),file=sys.stderr)
                        raise Exception("Empty feature! Not allowed!")
                    s.append(feature_s)
            else:
                s.append(str(feature))


        if forclassifier:
            s.append( targetpattern.tostring(targetdecoder) )
        return "\t".join(s)

    def savemosesphrasetable(self, filename, sourcedecoder, targetdecoder):
        """Output for moses"""
        with open(filename,'w',encoding='utf-8') as f:
            for sourcepattern, targetpattern, features in self:
                f.write(sourcepattern.tostring(sourcedecoder) + " ||| " + targetpattern.tostring(targetdecoder) + " ||| ")
                for i, feature, featureconf in enumerate(zip(features, self.conf.scorefeatures())):
                    if (i > 0): f.write(" ")
                    f.write(str(feature))
                f.write("\n")

    def loadmosesphrasetable(self, filename, sourceencoder, targetencoder,constrainsourcemodel=None,constraintargetmodel=None, quiet=False, reverse=False, delimiter="|||", score_column = 3, max_sourcen = 0, scorefilter = lambda x:True):
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


        added = 0
        skipped = 0

        haswordalignments = False

        while True:
            if not quiet:
                linenum += 1
                if (linenum % 100000) == 0:
                    print("Loading phrase-table: @" + str(linenum) + "\t(" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ") total added: " + str(added) + ", skipped: " + str(skipped),file=sys.stderr)
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
                scores = [ float(x) for x in segments[score_column-1].strip().split()  ]
            else:
                scores = []


            #if align2_column > 0:
            #    try:
            #        null_alignments = segments[align2_column].count("()")
            #    except:
            #        null_alignments = 0
            #else:
            #    null_alignments = 0

            if scorefilter:
                if not scorefilter(scores): continue

            if len(segments) >= 4:
                scores.append( [ tuple([int(y) for y in x.split('-')]) for x in segments[3].split() ] )
                haswordalignments = True
            elif haswordalignments:
                scores.append([])


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

            if constrainsourcemodel and source not in constrainsourcemodel:
                skipped += 1
                continue
            if constraintargetmodel and target not in constraintargetmodel :
                skipped += 1
                continue

            added += 1
            self.add(source,target, scores)

        f.close()

        self.conf = FeatureConfiguration()
        l = len(scores)
        if haswordalignments:
            l = l - 1
        for x in range(0,l):
            self.conf.addfeature(float,True,False) #score: True, classifier: False
        if haswordalignments:
            self.conf.addfeature(list)

    def patternswithindexes(self, sourcemodel, targetmodel, showprogress=True):
        """Finds occurrences (positions in the source and target models) for all patterns in the alignment model. """
        l = len(self)
        for i, sourcepattern in enumerate(self.sourcepatterns()):
            if showprogress:
                print("@" + str(i+1) + "/" + str(l), " " , round(((i+1)/l)*100,2),'%', file=sys.stderr)
            occurrences = 0
            if not sourcepattern in sourcemodel:
                continue

            tmpdata = defaultdict(list)

            sourceindexes = None #loading deferred until really needed
            for targetpattern in self.targetpatterns(sourcepattern):
                #print("DEBUG targetpattern=", sourcepattern,file=sys.stderr)
                if not targetpattern in targetmodel:
                    continue

                if not sourceindexes: #loading deferred until here to improve performance, preventing unnecessary loads
                    sourceindexes = defaultdict(list)
                    for sourcesentence, sourcetoken in sourcemodel[sourcepattern]:
                        sourceindexes[sourcesentence].append(sourcetoken)

                targetindexes = defaultdict(list)
                for targetsentence, targettoken in targetmodel[targetpattern]:
                    if targetsentence in sourceindexes:
                        targetindexes[targetsentence].append(targettoken)

                ptsscore = self[(sourcepattern,targetpattern)][0][2] #assuming moses style score vector!

                #for every occurrence of this pattern in the source
                for sentence in targetindexes:
                    #print("DEBUG sourceindex=", (sentence,token),file=sys.stderr)
                    #is a target pattern found in the same sentence? (if so we *assume* they're aligned, we don't actually use the word alignments anymore here)
                    for token in sourceindexes[sentence]:
                        for targettoken in targetindexes[sentence]:
                            tmpdata[(sentence,token,targettoken)].append( (ptsscore, sourcepattern, targetpattern) )
                            #yield sourcepattern, targetpattern, sentence, token, sentence, targettoken
                            break #multiple possible matches in same sentence? just pick first one... no word alignments here to resolve this

            #make sure only the strongest targetpattern for a given occurrence is chosen, in case multiple options exist
            for (sentence,token, targettoken),targets  in tmpdata.items():
                ptsscore,sourcepattern, targetpattern = sorted(targets)[-1] #sorted by ptsscore, last item will be highest
                occurrences += 1
                yield sourcepattern, targetpattern, sentence, token, sentence, targettoken

            if showprogress:
                print("\tFound " + str(occurrences) + " occurrences", file=sys.stderr)


    def extractcontextfeatures(self, sourcemodel, targetmodel, factoredcorpora):
        featurevector = []
        assert isinstance(sourcemodel, colibricore.IndexedPatternModel)
        assert isinstance(targetmodel, colibricore.IndexedPatternModel)

        factorconf = [x for x in self.conf if x[0] is colibricore.Pattern ]
        if len(factoredcorpora) != len(factorconf):
            raise ValueError("Expected " + str(len(factorconf)) + " instances in factoredcorpora, got " + str(len(factoredcorpora)))

        if not all([ isinstance(x,colibricore.IndexedCorpus) for x in factoredcorpora]):
            raise ValueError("factoredcorpora elements must be instances of IndexedCorpus")

        prev = None
        tmpdata = defaultdict(int) # featurevector => occurrencecount


        count = 0

        extracted = 0
        for sourcepattern, targetpattern, sentence, token,_,_ in self.patternswithindexes(sourcemodel, targetmodel):
            count+=1
            n = len(sourcepattern)

            if (sourcepattern, targetpattern) != prev:
                if prev:
                    #process previous
                    newfeaturevectors = []
                    featurevectors = self[prev]
                    assert len(featurevectors) == 1 #assuming only one featurevectors exists (will be expanded into multiple, one per occurrence, by the algorithm here
                    scorevector = featurevectors[0] #traditional moses score vector
                    for featurevector, count in tmpdata.items():
                        featurevector = list(featurevector)
                        newfeaturevectors.append(scorevector + featurevector + [count])
                    yield prev[0], prev[1], newfeaturevectors, scorevector

                tmpdata = defaultdict(int) #reset
                prev = (sourcepattern,targetpattern)

            featurevector = [] #local context features

            for factoredcorpus, factor in zip(factoredcorpora, factorconf):
                _,classdecoder, leftcontext, focus, rightcontext = factor
                sentencelength = factoredcorpus.sentencelength(sentence)
                for i in range(token - leftcontext,token):
                    if i < 0:
                        unigram = colibricore.BEGINPATTERN
                    else:
                        unigram = factoredcorpus[(sentence,i)]
                    assert len(unigram) == 1
                    featurevector.append(unigram)
                if focus:
                    focuspattern = factoredcorpus[(sentence,token):(sentence,token+n)]
                    assert len(focuspattern) >= 1
                    featurevector.append(focuspattern)
                for i in range(token + n , token + n + rightcontext):
                    if i >= sentencelength:
                        unigram = colibricore.ENDPATTERN
                    else:
                        unigram = factoredcorpus[(sentence,i)]
                    assert len(unigram) == 1
                    featurevector.append(unigram)

            #print(featurevector,file=sys.stderr)
            extracted += 1
            tmpdata[tuple(featurevector)] += 1

        #process final pair:
        if prev:
            #process previous
            newfeaturevectors = []
            featurevectors = self[prev]
            assert len(featurevectors) == 1 #assuming only one featurevectors exists (will be expanded into multiple, one per occurrence, by the algorithm here
            scorevector = featurevectors[0] #traditional moses score vector
            for featurevector, count in tmpdata.items():
                featurevector = list(featurevector)
                newfeaturevectors.append(scorevector + featurevector + [count])
            yield prev[0], prev[1], newfeaturevectors, scorevector


        print("Extracted features for " + str(extracted) + " sentences",file=sys.stderr)

    def addcontextfeatures(self, sourcemodel, targetmodel, factoredcorpora):
        for sourcepattern, targetpattern, newfeaturevectors,_ in self.extractcontextfeatures(sourcemodel, targetmodel, factoredcorpora):
            self[(sourcepattern,targetpattern)] = newfeaturevectors

    def normalize(self, sumover='s'):
        if self.singleintvalue:
            raise Exception("Can't normalize AlignedPatternDict with singleintvalue set")

        total = {}

        for sourcepattern, targetpattern, features in self:
            #if not isinstance(value, list) and not isinstance(value, tuple):
            #    print("ERROR in normalize(): Expected iterable, got " + str(type(value)),file=sys.stderr)
            #    continue

            for i in range(0, min(len(features), len(sumover))):
                if sumover[i] == 's': #s|t
                    if not i in total:
                        total[i] = colibricore.PatternDict_float()
                    total[i][targetpattern] = total[i][targetpattern] + features[i]
                elif sumover[i] == 't': #t|s
                    if not i in total:
                        total[i] = colibricore.PatternDict_float()
                    total[i][sourcepattern] = total[i][sourcepattern] + features[i]



        for sourcepattern, targetpattern, features in self:
            #if not isinstance(value, list) and not isinstance(value, tuple):
            #    print("ERROR in normalize(): Expected iterable, got " + str(type(value)),file=sys.stderr)
            #    continue
            #print("f: ", features,file=sys.stderr)
            for i in range(0,min(len(features),len(sumover))):
                if sumover[i] == 's': #s|t
                    try:
                        #print("s: ", features[i],"/",total[i][targetpattern],file=sys.stderr)
                        features[i] = features[i] / total[i][targetpattern]
                    except ZeroDivisionError: #ok, just leave unchanged
                        pass
                elif sumover[i] == 't': #t|s
                    try:
                        #print("t: ", features[i],"/",total[i][sourcepattern],file=sys.stderr)
                        features[i] = features[i] / total[i][sourcepattern]
                    except ZeroDivisionError: #ok, just leave unchanged
                        pass
                elif sumover[i] == '0':
                    features[i] = 0
                elif sumover[i] == '-':
                    pass


def mosesphrasetable2alignmodel(inputfilename,sourceclassfile, targetclassfile, outfileprefix, constrainsourcemodel=None, constraintargetmodel=None,pst=0.0, pts = 0.0,nonorm=False, quiet=False):
    if not quiet: print("Reading source encoder " + sourceclassfile,file=sys.stderr)
    sourceencoder = colibricore.ClassEncoder(sourceclassfile)
    if not quiet: print("Reading target encoder " + targetclassfile,file=sys.stderr)
    targetencoder = colibricore.ClassEncoder(targetclassfile)
    if not quiet: print("Initialising featured alignment model",file=sys.stderr)
    model = FeaturedAlignmentModel()
    if not quiet: print("Loading moses phrasetable",file=sys.stderr)
    if pts or pst:
        scorefilter = lambda scores: scores[2] > pts and scores[0] > pst
    else:
        scorefilter = None
    model.loadmosesphrasetable(inputfilename, sourceencoder, targetencoder, constrainsourcemodel, constraintargetmodel, False,False, "|||", 3, 0, scorefilter)
    if not quiet: print("Loaded " + str(len(model)) + " source patterns")
    if not nonorm and (constrainsourcemodel or constraintargetmodel or pst or pts):
        if not quiet: print("Normalising",file=sys.stderr)
        model.normalize('s-t-')
    if not quiet: print("Saving alignment model",file=sys.stderr)
    model.save(outfileprefix)


def main_mosesphrasetable2alignmodel():
    parser = argparse.ArgumentParser(description="Convert Moses phrasetable to Colibri alignment model", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i','--inputfile',type=str,help="Input phrasetable", action='store',required=True)
    parser.add_argument('-o','--outputfile',type=str,help="Output alignment model (file prefix without .colibri.alignmodel-* extension)", action='store',required=True)
    parser.add_argument('-S','--sourceclassfile',type=str,help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile',type=str,help="Target class file", action='store',required=True)
    parser.add_argument('-m','--constrainsourcemodel',type=str,help="Source patternmodel, used to constrain possible patterns", action='store',required=False)
    parser.add_argument('-M','--constraintargetmodel',type=str,help="Target patternmodel, used to constrain possible patterns", action='store',required=False)
    parser.add_argument('-p','--pts',type=float,help="Constrain by minimum probability p(t|s)",default=0.0, action='store',required=False)
    parser.add_argument('-P','--pst',type=float,help="Constrain by minimum probability p(s|t)", default=0.0,action='store',required=False)
    parser.add_argument('-N','--nonorm',help="Disable normalisation", default=False,action='store_true',required=False)
    args = parser.parse_args()

    if args.constrainsourcemodel:
        print("Loadin source model for constraints",file=sys.stderr)
        constrainsourcemodel = colibricore.UnindexedPatternModel(args.constrainsourcemodel)
    else:
        constrainsourcemodel = None

    if args.constraintargetmodel:
        print("Loading target model for constraints",file=sys.stderr)
        constraintargetmodel = colibricore.UnindexedPatternModel(args.constraintargetmodel)
    else:
        constraintargetmodel = None

    mosesphrasetable2alignmodel(args.inputfile, args.sourceclassfile, args.targetclassfile, args.outputfile, constrainsourcemodel, constraintargetmodel, args.pst, args.pts,args.nonorm)

def main_extractfeatures():
    parser = argparse.ArgumentParser(description="Extract context features and add to alignment model", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i','--inputfile',type=str,help="Input alignment model (file prefix without .colibri.alignmodel-* extension)", action='store',required=True)
    parser.add_argument('-o','--outputfile',type=str,help="Output alignment model (file prefix without .colibri.alignmodel-* extension, or directory when used with -C)", action='store',required=True)
    parser.add_argument('-s','--sourcemodel',type=str,help="Source model (indexed pattern model)", action='store',required=True)
    parser.add_argument('-t','--targetmodel',type=str,help="Target model (indexed pattern model)", action='store',required=True)
    parser.add_argument('-S','--sourceclassfile',type=str,help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile',type=str,help="Target class file", action='store',required=True)
    parser.add_argument('-f','--corpusfile',type=str,help="Corpus input file for feature extraction, may be specified multiple times, but all data files must cover the exact same data, i.e. have exactly the same indices (describing different factors)", action='append',required=True)
    parser.add_argument('-c','--classfile',type=str,help="Class file for the specified data file (may be specified multiple times, once per -f)", action='append',required=True)
    parser.add_argument('-l','--leftsize',type=int,help="Left context size (may be specified multiple times, once per -f)", action='append',required=True)
    parser.add_argument('-r','--rightsize',type=int,help="Right context size (may be specified multiple times, once per -f)", action='append',required=True)
    parser.add_argument('-C','--buildclassifiers',help="Build classifier training data, one classifier expert per pattern, specify a working directory in -o", action='store_true',default=False)
    parser.add_argument('-w','--weighbyoccurrence',help="When building classifier data (-C), use exemplar weighting to reflect occurrence count, rather than duplicating instances", action='store_true',default=False)
    parser.add_argument('-W','--weighbyscore',help="When building classifier data (-C), use exemplar weighting to weigh in p(t|s) from score vector", action='store_true',default=False)
    parser.add_argument('-I','--instancethreshold',type=int,help="Classifiers (-C) having less than the specified number of instances will be not be generated", action='store',default=2)
    parser.add_argument('-X','--experts', help="Classifier experts, one per source pattern", action="store_true", default=False)
    parser.add_argument('-M','--monolithic', help="Monolithic classifier", action="store_true", default=False)
    args = parser.parse_args()

    if not (len(args.corpusfile) == len(args.classfile) == len(args.leftsize) == len(args.rightsize)):
        print("Number of mentions of -f, -c, -l and -r has to match",file=sys.stderr)
        sys.exit(2)


    print("Loading alignment model",file=sys.stderr)
    model = FeaturedAlignmentModel()
    model.load(args.inputfile)


    print("Loading source decoder " + args.sourceclassfile,file=sys.stderr)
    sourcedecoder = colibricore.ClassDecoder(args.sourceclassfile)
    print("Loading target decoder " + args.targetclassfile,file=sys.stderr)
    targetdecoder = colibricore.ClassDecoder(args.targetclassfile)
    print("Loading source model " , args.sourcemodel, file=sys.stderr)
    sourcemodel = colibricore.IndexedPatternModel(args.sourcemodel)

    print("Loading target model ", args.targetmodel, file=sys.stderr)
    targetmodel = colibricore.IndexedPatternModel(args.targetmodel)

    corpora = []
    for corpusfile in args.corpusfile:
        print("Loading corpus file ", corpusfile, file=sys.stderr)
        corpora.append(colibricore.IndexedCorpus(corpusfile))

    #classdecoders = []
    #for classfile in args.classfile:
    #    print("Loading corpus file ", classfile, file=sys.stderr)
    #    classdecoders.append(colibricore.ClassDecoder(classfile))


    #add context configuration
    for corpus, classfile,left, right in zip(corpora,args.classfile,args.leftsize, args.rightsize):
        model.conf.addcontextfeature(classfile,left,True, right)

    #store occurrence info in feature vector (appended to score features)
    model.conf.addfeature(int,False,False) #occurrence count for context configuration

    print("Configuration:",model.conf.conf,file=sys.stderr)

    if args.buildclassifiers:
        if not args.monolithic and not args.experts:
            args.experts = True

        if not os.path.isdir(args.outputfile):
            try:
                os.mkdir(args.outputfile)
            except:
                print("Unable to build directory " + args.outputfile,file=sys.stderr)
                sys.exit(2)

        model.conf.loaddecoders(sourcedecoder,targetdecoder)

        f = None
        prevsourcepattern = None
        firsttargetpattern = None
        prevtargetpattern = None
        trainfile = ""
        if args.monolithic:
            f = open(args.outputfile + "/train",'w',encoding='utf-8')
            f2 = open(args.outputfile + "/sourcepatterns.list",'w',encoding='utf-8')

        fconf = open(args.outputfile + "/classifier.conf",'wb')

        classifierconf = { 'leftsize': args.leftsize, 'rightsize': args.rightsize, 'weighbyoccurrence': args.weighbyoccurrence, 'weighbyscore': args.weighbyscore, 'experts': args.experts, 'monolithic': args.monolithic, 'featureconf': model.conf}
        pickle.dump(classifierconf, fconf)
        fconf.close()


        for sourcepattern, targetpattern, featurevectors, scorevector in model.extractcontextfeatures(sourcemodel, targetmodel, corpora):
            if prevsourcepattern is None or sourcepattern != prevsourcepattern:
                #write previous buffer to file:
                if prevsourcepattern and firsttargetpattern and prevtargetpattern and firsttargetpattern != prevtargetpattern:
                    #only bother if there are at least two distinct target options
                    if len(buffer) < args.instancethreshold:
                        print("Omitting " + trainfile + ", only " + str(len(buffer)) + " instances",file=sys.stderr)
                    else:
                        sourcepattern_s = prevsourcepattern.tostring(sourcedecoder)
                        trainfile = args.outputfile + "/" + quote_plus(sourcepattern_s) + ".train"
                        print("Writing " + trainfile,file=sys.stderr)
                        if args.experts:
                            f = open(trainfile,'w',encoding='utf-8')
                        elif args.monolithic:
                            f2.write(sourcepattern_s+"\n")
                        for line, occurrences,pts in buffer:
                            if args.weighbyscore:
                                f.write(line + "\t" + str(occurrences*pts) +  "\n")
                            elif args.weighbyoccurrence:
                                f.write(line + "\t" + str(occurrences) +  "\n")
                            else:
                                for i in range(0,occurrences):
                                    f.write(line + "\n")
                        if args.experts:
                            f.close()

                buffer = []
                prevsourcepattern = sourcepattern
                firsttargetpattern = targetpattern

            for featurevector in featurevectors:
                #last feature holds occurrence count:
                buffer.append( (model.itemtostring(sourcepattern, targetpattern, featurevector,sourcedecoder, targetdecoder,False,True,False), featurevector[-1],scorevector[2] )  )

            prevtargetpattern = targetpattern


        #write last one to file:
        if prevsourcepattern and firsttargetpattern and prevtargetpattern and firsttargetpattern != prevtargetpattern:
            #only bother if there are at least two distinct target options
            if len(buffer) < args.instancethreshold:
                print("Omitting " + trainfile + ", only " + str(len(buffer)) + " instances",file=sys.stderr)
            else:
                sourcepattern_s = prevsourcepattern.tostring(sourcedecoder)
                trainfile = args.outputfile + "/" + quote_plus(sourcepattern_s) + ".train"
                print("Writing " + trainfile,file=sys.stderr)
                if args.experts:
                    f = open(trainfile,'w',encoding='utf-8')
                for line, occurrences,pts in buffer:
                    if args.weighbyscore:
                        f.write(line + "\t" + str(occurrences*pts) +  "\n")
                    elif args.weighbyoccurrence:
                        f.write(line + "\t" + str(occurrences) +  "\n")
                    else:
                        for i in range(0,occurrences):
                            f.write(line + "\n")
                if args.experts:
                    f.close()

        if args.monolithic:
            f.close()
            f2.close()

    else:
        print("Extracting and adding context features from ", corpusfile, file=sys.stderr)
        model.addcontextfeatures(sourcemodel, targetmodel, corpora)

        print("Saving alignment model", file=sys.stderr)
        model.save(args.outputfile)



def main_alignmodel():
    parser = argparse.ArgumentParser(description="Load and view the specified alignment model", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i','--inputfile',type=str,help="Input alignment model (file prefix without .colibri.alignmodel-* extension)", action='store',required=True)
    parser.add_argument('-S','--sourceclassfile',type=str,help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile',type=str,help="Target class file", action='store',required=True)
    parser.add_argument('-p','--pts',type=float,help="Constrain by minimum probability p(t|s), assumes a moses-style score vector",default=0.0, action='store',required=False)
    parser.add_argument('-P','--pst',type=float,help="Constrain by minimum probability p(s|t), assumes a moses-style score vector", default=0.0,action='store',required=False)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar


    print("Loading source decoder " + args.sourceclassfile,file=sys.stderr)
    sourcedecoder = colibricore.ClassDecoder(args.sourceclassfile)
    print("Loading target decoder " + args.targetclassfile,file=sys.stderr)
    targetdecoder = colibricore.ClassDecoder(args.targetclassfile)
    print("Loading alignment model",file=sys.stderr)
    if os.path.exists(args.inputfile + ".colibri.alignmodel-featconf"):
        model = FeaturedAlignmentModel()
    else:
        model = AlignmentModel()
    model.load(args.inputfile)
    print("Outputting",file=sys.stderr)
    if args.pts or args.pst:
        scorefilter = lambda scores: scores[2] > args.pts and scores[0] > args.pst
    else:
        scorefilter = None
    model.output(sourcedecoder,targetdecoder,scorefilter)




