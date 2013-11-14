#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import
import colibricore

def extractskipgrams(alignmodel,tmpdir="./", maxlength= 8):
    sourcepatternfile = tmpdir + "/sourcepatterns.colibri.dat"
    with open(sourcepatternfile,'wb'):
        for sourcepattern in alignmodel.sourcepatterns():
            f.write(bytes(sourcepattern) + '\0')


    targetpatternfile = tmpdir + "/targetpatterns.colibri.dat"
    with open(targetpatternfile,'wb'):
        for targetpattern in alignmodel.targetpatterns():
            f.write(bytes(targetpattern) + '\0')

    options = colibricore.PatternModelOptions()
    options.MINTOKENS = 2
    options.MAXLENGTH = maxlength
    options.DOSKIPGRAMS = True

    sourcemodel = colibri.IndexedPatternModel()
    sourcemodel.train(sourcepatternfile,options)

    targetmodel = colibri.IndexedPatternModel()
    targetmodel.train(targetpatternfile,options)

    for sourcepattern, targetpattern, features in alignmodel.items():
        if sourcepattern in sourcemodel:


