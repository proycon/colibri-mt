#!/usr/bin/env python3

import colibricore

sourceencoder = colibricore.ClassEncoder()

s1 = sourceencoder.buildpattern("het grote huis", False, True)
s2 = sourceencoder.buildpattern("het paleis", False, True)
t1 = sourceencoder.buildpattern("the big house", False, True)
t2 = sourceencoder.buildpattern("the grand house", False, True)
t3 = sourceencoder.buildpattern("the palace", False, True)

model = colibricore.AlignmentModel()
model.add(s1,t1,[1,0,1,0])
model.add(s1,t2,[1,0,1,0])
model.add(s2,t2,[1,0,1,0])
model.add(s2,t3,[1,0,1,0])
model.normalize('s-t-')


