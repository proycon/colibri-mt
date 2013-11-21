#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import
import colibricore

from colibrimt.alignmentmodel import FeaturedAlignmentModel

sourceencoder = colibricore.ClassEncoder()
targetencoder = colibricore.ClassEncoder()

s1 = sourceencoder.buildpattern("het grote huis", False, True)
s2 = sourceencoder.buildpattern("het paleis", False, True)
t1 = targetencoder.buildpattern("the big house", False, True)
t2 = targetencoder.buildpattern("the grand house", False, True)
t3 = targetencoder.buildpattern("the palace", False, True)

sourceencoder.save('/tmp/s.cls')
targetencoder.save('/tmp/t.cls')
sd = colibricore.ClassDecoder('/tmp/s.cls')
td = colibricore.ClassDecoder('/tmp/t.cls')

model = FeaturedAlignmentModel()
model.add(s1,t1,[1,0,1,0])
model.add(s1,t2,[1,0,1,0])
model.add(s2,t2,[1,0,1,0])
model.add(s2,t3,[1,0,1,0])
model.normalize('s-t-')

for source, target,scores in model:
    print(source.tostring(sd)+"\t"+target.tostring(td)+"\t" + " ".join([str(x) for x in scores]))

