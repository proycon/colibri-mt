#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import
import colibricore
import os
import sys

def extractskipgrams(alignmodel,tmpdir="./", maxlength= 8, mintokens = 2):
    sourcepatternfile = tmpdir + "/sourcepatterns.colibri.dat"
    with open(sourcepatternfile,'wb') as f:
        for sourcepattern in alignmodel.sourcepatterns():
            f.write(bytes(sourcepattern) + '\0')


    targetpatternfile = tmpdir + "/targetpatterns.colibri.dat"
    with open(targetpatternfile,'wb') as f:
        for targetpattern in alignmodel.targetpatterns():
            f.write(bytes(targetpattern) + '\0')

    options = colibricore.PatternModelOptions()
    options.MINTOKENS = mintokens
    options.MAXLENGTH = maxlength
    options.DOSKIPGRAMS = True

    sourcemodel = colibricore.IndexedPatternModel()
    sourcemodel.train(sourcepatternfile,options)

    targetmodel = colibricore.IndexedPatternModel()
    targetmodel.train(targetpatternfile,options)

    tmpalignmodel = colibricore.AlignmentModel()

    for sourcepattern, targetpattern, features in alignmodel.items():
        if sourcepattern in sourcemodel:
            #find abstractions
            sourcetemplates = []
            targettemplates = []

            for template in sourcemodel.getsubsumptionparents(sourcepattern):
                if template.category() == colibricore.PatternCategory.SKIPGRAM and sourcemodel[template] >= mintokens:
                    sourcetemplates.append(template)

            for template in targetmodel.getsubsumptionparents(targetpattern):
                if template.category() == colibricore.PatternCategory.SKIPGRAM and targetmodel[template] >= mintokens:
                    targettemplates.append(template)




    os.unlink(sourcepatternfile)
    os.unlink(targetpatternfile)
