#!/usr/bin/env python

# Author: Tobias Daeullary, t-dae[at]live.de

import sys
import os.path
import math
import fnmatch
import itertools
import copy
from string import digits


# PARAMS
xMinOffset = 500                            # if single group, min offset by this
yOffset = -50                               # basic pin offset (=~ GRID!)
gridSize = math.fabs(yOffset)

pinGroupSanitize = 5                      # merge groups if first X chars are the same (only if groupname > X)
yGroupOffset = int(3 * yOffset)
pinLength = int(4 * gridSize)
pinTextSize = int(gridSize / 2)

singleGroups = False                        # do not make 1 big device, but spread out the pin groups on a plane
makeRec = True                             # Rectangle around groups, only effective if singleGroups = True
makeUnits = True                           # whether to tag groups as Kicad-Units A, B, ... only effective if singleGroups = True

# Pin types
pwrPinGND = ['GND*', 'VSS*']                # orientation: bottom
pwrPinVDD = ['VDD*', 'VCC*', 'VR*']         # orientation: top
clkPin = ['*CLK*', '*CK*']
ncPin = ['NC']                              # orientation: right

# additional text to display after pinFunction; column IDs (first is 0) as in pdf/txt
addTxt = [10]


class Pin:
    def __init__(self, pinID, pinFunction, pinGroup, symbol, orientation, aTxt):
        self.pinID = pinID
        self.pinFunction = pinFunction
        self.pinGroup = pinGroup
        self.symbol = symbol
        self.orientation = orientation
        self.actualGroup = pinGroup
        self.addTxt = aTxt
        
class FP:
    def __init__(self, name, sanitize):
        self.name = name
        self.pins = []
        self.pinGroups = []
        self.groupTypes = []
        self.san = sanitize
        self.gSizes = {}
        self.gMaxTxtExtents = {}
        self.gUnitMapping = {}
        self.phySize = []
        
    def updateMapping(self, increment):
        idx = 1
        p = False
        if len(self.pinGroups) > 26 and increment:
            print 'Warning: Kicad units active but too many pin groups found ({} vs. 26 allowed). \n'.format(str(len(self.pinGroups))), \
                    'Maybe decrease \'pinGroupSanitize\' parameter?\npin groups:\n\tpGroup\tLength\tKicad Unit'
            p = True
        for grp in self.pinGroups:
            self.gUnitMapping.update({grp : idx})
            if p:
                print '\t', grp, '\t', self.getGroupSize(grp), '\t', chr(idx + 64)
            if increment and idx < 26:
                idx += 1
            
    def getGroupSize(self, group):
        size = 0
        for pin in self.pins:
            if pin.actualGroup == group:
                size += 1
        self.gSizes.update({group : size})
        return size
        
    def getGroupNumber(self):
        return len(self.pinGroups)
        
    def setGroupOrientation(self, group, orientation):
        maxTxtLen = 0
        for pin in self.pins:
            if pin.actualGroup == group:
                self.pins[self.pins.index(pin)].orientation = orientation
                if maxTxtLen <= len(pin.pinFunction) + len(pin.addTxt):
                    maxTxtLen = len(pin.pinFunction) + len(pin.addTxt)
                    
        self.gMaxTxtExtents.update({group : maxTxtLen})

    def calcPhysLayout(self, tPins, bPins, rPins, lPins, xPins, groupOffset, pinOffset, txtSize, pLength):
        # rule: top & bottom are fixed + reserved for GND and VDD
        self.gSize = {}
        self.gMaxTxtExtents = {}
        gOffset = math.fabs(groupOffset)
        pOffset = math.fabs(pinOffset)
        bSize = -1 * (gOffset - pOffset)
        tSize = -1 * (gOffset - pOffset)
        rSize = -1 * (gOffset - pOffset)
        lSize = -1 * (gOffset - pOffset)
        toSort = {}
        for grp in self.pinGroups:
            gSize = self.getGroupSize(grp)
            #print 'group:', grp, gSize
            if any(fnmatch.fnmatch(grp, s) for s in bPins):
                bSize += gSize * pOffset + gOffset
                self.setGroupOrientation(grp, 'U')
            elif any(fnmatch.fnmatch(grp, s) for s in tPins):
                tSize += gSize * pOffset + gOffset
                self.setGroupOrientation(grp, 'D')
            elif any(fnmatch.fnmatch(grp, s) for s in lPins):
                lSize += gSize * pOffset + gOffset
                self.setGroupOrientation(grp, 'R')
            elif any(fnmatch.fnmatch(grp, s) for s in rPins):
                rSize += gSize * pOffset + gOffset
                self.setGroupOrientation(grp, 'L')
            else:
                toSort.update({grp : gSize})
        
        sHash = sorted(toSort, key=toSort.get, reverse=True)
        sumSpace = sum(toSort.values()) * pOffset + len(sHash) * gOffset
        idx = 0
        while idx < len(sHash):
            if lSize < sumSpace / 2:
                lSize += toSort.get(sHash[idx]) * pOffset + gOffset
                self.setGroupOrientation(sHash[idx], 'R')
            else:
                rSize += toSort.get(sHash[idx]) * pOffset + gOffset
                self.setGroupOrientation(sHash[idx], 'L')
            idx += 1
        
        tTxtLen = 0
        bTxtLen = 0
        rTxtLen = 0
        lTxtLen = 0
        for pin in self.pins:
            if pin.orientation == 'U' and len(pin.pinFunction) + len(pin.addTxt) >= bTxtLen:
                bTxtLen = len(pin.pinFunction) + len(pin.addTxt)
            if pin.orientation == 'D' and len(pin.pinFunction) + len(pin.addTxt) >= tTxtLen:
                tTxtLen = len(pin.pinFunction) + len(pin.addTxt)
            if pin.orientation == 'L' and len(pin.pinFunction) + len(pin.addTxt) >= rTxtLen:
                rTxtLen = len(pin.pinFunction) + len(pin.addTxt)
            if pin.orientation == 'R' and len(pin.pinFunction) + len(pin.addTxt) >= lTxtLen:
                lTxtLen = len(pin.pinFunction) + len(pin.addTxt)
        if tSize >= bSize:
            tSize += (rTxtLen + lTxtLen) * txtSize + 2 * math.fabs(pLength)
            tOffset = lTxtLen * txtSize + math.fabs(pLength)
            bOffset = 0
        else:
            bSize += (rTxtLen + lTxtLen) * txtSize + 2 * math.fabs(pLength)
            bOffset = lTxtLen * txtSize + math.fabs(pLength)
            tOffset = 0
            
        if rSize >= lSize:
            rSize += 2 * math.fabs(pLength) + gOffset
            rOffset = gOffset
            lOffset = 0
        else:
            lSize += 2 * math.fabs(pLength) + gOffset
            lOffset = gOffset
            rOffset = 0
        
        #print 'calculated b, t, l, r:', bSize, tSize, lSize, rSize
        self.phySize = [tSize, bSize, lSize, rSize]
        return [tSize, bSize, lSize, rSize, tOffset, bOffset, lOffset, rOffset]
        
        
    def addPin(self, pinID, pinFunction, pinGroup, symbol, orientation, aTxt):
        newpin = Pin(pinID, pinFunction, pinGroup, symbol, orientation, aTxt)
        # check for 'actual' groups which only differ by their last char
        if not newpin.pinGroup == '' and len(newpin.pinGroup) <=  self.san:
            if newpin.pinGroup not in self.pinGroups:
                self.pinGroups.append(newpin.pinGroup)
        else:
            if not newpin.pinGroup == '':
                refString = newpin.pinGroup
                #print 'gsan'
            else:
                refString = newpin.pinFunction
                #print 'fsan'
            if refString not in self.pinGroups:
                matchGroups = refString[:self.san] + '*'
                if matchGroups in self.pinGroups:
                    #print matchGroups, 'found!'
                    grpIdx = self.pinGroups.index(matchGroups)
                    newpin.actualGroup = self.pinGroups[grpIdx]
                else:
                    #print 'curr groups:', self.pinGroups
                    #print 'curr matchGroups:', matchGroups
                    merge = False
                    for grp in self.pinGroups:
                        if grp.startswith(matchGroups[:-1]) and len(grp) > self.san and len(matchGroups) == self.san + 1:
                            # mergeable group found!
                            #print matchGroups, ': merge happening!'
                            merge = True
                            self.pinGroups[self.pinGroups.index(grp)] = matchGroups
                            for pin in self.pins:
                                if pin.actualGroup.startswith(matchGroups[:-1]) and len(pin.actualGroup) > self.san \
                                        and not pin.actualGroup == matchGroups:
                                    self.pins[self.pins.index(pin)].actualGroup = matchGroups
                    if merge:               
                        newpin.actualGroup = matchGroups
                    else:
                        newpin.actualGroup = refString
                        self.pinGroups.append(refString)
            else:
                newpin.actualGroup = refString
             
        pinIdx = len(self.pins)
        for k, pin in enumerate(self.pins):
            if pin.actualGroup == newpin.actualGroup:
                pinIdx = k
        self.pins.insert(pinIdx, newpin)
        #print '\n\npin:', newpin.pinID, 'curr grps:', self.pinGroups
                

# functions
def find_all(a_str, sub):
    start = 0
    while True:
        start = a_str.find(sub, start)
        if start == -1: 
            return
        yield start
        start += len(sub)
        

# cmd-line input
argc = len(sys.argv)
cmdaddTxt = []
cmdSanit = -1
sourcePath = ''
destPath = ''
if argc == 1:
    print 'At least specify input .txt file! Call with -h for help!'
    quit()
if argc > 1:
    cidx = 1
    while cidx < argc:
        if sys.argv[cidx] == '-h':
            print 'Command line options (optional in [brackets]):\n', \
                ' python alteraFP2escheema.py [<options>] <input file path> [<output file path>]\n', \
                '\t If <output file path> matches existing lib, part(s) will be added to this lib.\n', \
                '\tAv. options:\n', \
                '\t -a:\t specify column IDs in .txt/.pdf you want to \n', \
                '\t\tinclude as pin function text (1st col ID is 0)\n\t\te.g. -a 8,10,11\n', \
                '\t\tWarning: too many chars and Kicad cannot load library!\n', \
                '\t -s:\t pinGroupSanitize: if first n chars of pinFunction\n', \
                '\t\tare the same, group together\n\t\te.g. -s 4\n'
            quit()
        if sys.argv[cidx] == '-a':
            if cidx == argc - 1:
                print 'Not enough arguments! Call with -h for help!'
                quit()
            cmdaddTxt = [int(n) for n in sys.argv[cidx + 1].split(',')]
            cidx += 1
        elif sys.argv[cidx] == '-s':
            if cidx == argc - 1:
                print 'Not enough arguments! Call with -h for help!'
                quit()
            cmdSanit = int(sys.argv[cidx + 1])
            if cmdSanit < 0:
                print 'Wrong argument! Call with -h for help!'
                quit()
            cidx += 1
        elif sourcePath == '':
            sourcePath = sys.argv[cidx]
        else:
            destPath = sys.argv[cidx]
                       
        cidx += 1
            
if sourcePath == '':
    print 'Input .txt file not specified! Call with -h for help!'
    quit()
if destPath == '':
    destPath = sourcePath.strip('.txt') + '.lib'
    destOverride = True
else:
    destOverride = False
source = open(sourcePath, 'r')

if len(cmdaddTxt) > 0:
    addTxt = cmdaddTxt
if not cmdSanit == -1:
    pinGroupSanitize = cmdSanit

  
destNew = not(os.path.isfile(destPath)) or destOverride
oldTxt = ''
if not destNew:
    dest = open(destPath, 'r+')
    oldTxt = dest.read()
    backup = destPath.strip('.lib') + '_old.lib'
    if not os.path.isfile(backup):
        destOld = open(backup, 'w')
        destOld.write(oldTxt)
        destOld.close
else:
    dest = open(destPath, 'w')
    
FPs = []
currFP = None
ok = 0
device = ""
first = 1
for line in source:
    if line.startswith("\"Pin Information"):
        device = line.split()[6]
        continue
        
    if line.startswith("Bank Number"):
        if first == 0:
            idx = 1
            currFP.updateMapping(singleGroups and makeUnits)
            FPs.append(currFP) 
            
        ok = True
        currFP = FP(line.split("\t")[7], pinGroupSanitize)
        #print "\nreading Footprint:", currFP.name
        continue
    
    if line.startswith('Note') or line.strip() == '':
        ok = False
        continue
        
    if ok:
        first = 0
            
        currLine = line.split("\t")
        pF = currLine[2].strip('\"')
        pID = currLine[7].strip('\"')
        aTxt = ''
        for col in addTxt:
            if not currLine[col] == '':
                aTxt += ',' + currLine[col]
        
        if any(fnmatch.fnmatch(pF, s) for s in pwrPinGND):
            symbol = 'W'
            orientation = 'U'
        elif any(fnmatch.fnmatch(pF, s) for s in pwrPinVDD):
            symbol = 'W'
            orientation = 'D'
        elif any(fnmatch.fnmatch(pF, s) for s in clkPin):
            symbol = 'C C'
            orientation = ''
        elif any(fnmatch.fnmatch(pF, s) for s in ncPin):
            symbol = 'N'
            orientation = ''
        else:
            symbol = 'B'
            orientation = ''
            
        if singleGroups:
            orientation = 'R'
            
        pG = currLine[0] 
            
        currFP.addPin(pID, pF, pG, symbol, orientation, aTxt)
        
# last line
idx = 1
currFP.updateMapping(singleGroups and makeUnits)
FPs.append(currFP)

source.close()
print "Imported", device, "with", len(FPs), "device(s)"

# write into library

libTxt = ""
if destNew:
    libTxt = 'EESchema-LIBRARY Version 2.3\n' \
             '#encoding utf-8\n'             

FPID = 1
for FP in FPs:
    startPos = len(libTxt)
    #calcPhysLayout(self, tPins, bPins, rPins, lPins, xPins, groupOffset, pinOffset, pinTextSize, pinLength):
    print 'Calculating Layout of device', FPID, '...'
    if not singleGroups:
        dims = FP.calcPhysLayout(pwrPinVDD, pwrPinGND, ncPin, '', '', yGroupOffset, yOffset, pinTextSize, pinLength)
        if dims[0] >= dims[1]:
            sizeX = dims[0]
        else:
            sizeX = dims[1]
        if dims[2] >= dims[3]:
            sizeY = dims[2]
        else:
            sizeY = dims[3]
        # calc start pos + 'gridify'
        topX = int(round(((sizeX - dims[0]) / 2 - sizeX / 2) / gridSize) * gridSize + dims[4])
        topY = int(round((sizeY / 2) / gridSize) * gridSize)
        leftX = int(round((- sizeX / 2) / gridSize) * gridSize)
        leftY = int(round((-(sizeY - dims[2]) / 2 + sizeY / 2) / gridSize) * gridSize - dims[6])
        bottomX = int(round(((sizeX - dims[1]) / 2 - sizeX / 2) / gridSize) * gridSize + dims[5])
        bottomY = int(round((- sizeY / 2) / gridSize) * gridSize)
        rightX = int(round((sizeX / 2) / gridSize) * gridSize)
        rightY = int(round((-(sizeY - dims[3]) / 2 + sizeY / 2) / gridSize) * gridSize - dims[7])
        
    distX = 0
    distY = 0
    xOffsetOverride = xMinOffset
    lastGroup = FP.pins[0].actualGroup
    lastGroupSize = 0
    lastGroupIdx = 0
    lastGroupTxtLen = 0
    numGroups = 0
    currIdx = 0
    while currIdx < len(FP.pins):
        pin = FP.pins[currIdx]
        #print 'curr Pin:', pin.pinID, '\t\t', pin.pinFunction, '\t\t ->', pin.actualGroup
        if not(FP.pins[currIdx - 1].actualGroup == pin.actualGroup):
            currGroup = pin.actualGroup
                
            if singleGroups:
                # Rectangle
                if makeRec and not currIdx == 0:
                    libTxt += 'S {} {} {} {} {} 1 {} N\n' \
                                .format(str(distX + pinLength), str(int(distY - lastGroupSize * yOffset + gridSize)), \
                                str(int(distX + pinLength + lastGroupTxtLen * pinTextSize + gridSize)), \
                                str(int(distY)), str(FP.gUnitMapping.get(lastGroup)), int(pinTextSize / 5))
                
                if makeUnits:
                    distY = 0
                    distX = 0
                else:
                    if xOffsetOverride < pinLength + lastGroupTxtLen * pinTextSize + 2 * gridSize:
                        xOffsetOverride = int(pinLength + lastGroupTxtLen * pinTextSize + 2 * gridSize)
                        
                    if math.fabs(distX) + 500 > math.fabs(distY):
                        distY += yGroupOffset
                    else:
                        distX += xOffsetOverride
                        xOffsetOverride = xMinOffset
                        distY = 0
                        
                libTxt += 'T 0 {} {} {} 0 {} 0 {} Normal 0 L B\n' \
                    .format(str(distX + pinLength), str(int(distY - 1.5 * yOffset)), str(pinTextSize), str(FP.gUnitMapping.get(currGroup)), pin.actualGroup)
            
            else:
                # store new current values
                if not currIdx == 0:
                    if FP.pins[currIdx - 1].orientation == 'U':
                        if gSize > 1:
                            libTxt += 'T 900 {} {} {} 0 1 0 {} Normal 0 L C\n' \
                                .format(str(int(distX - (lastGroupSize + 1) * gridSize)), \
                                str(int(distY + pinLength + gridSize)), str(int(pinTextSize)), FP.pins[currIdx - 1].actualGroup)
                        bottomX = distX
                        bottomY = distY
                    elif FP.pins[currIdx - 1].orientation == 'D':
                        if gSize > 1:
                            libTxt += 'T 900 {} {} {} 0 1 0 {} Normal 0 R C\n' \
                                .format(str(int(distX - (lastGroupSize + 1) * gridSize)), \
                                str(int(distY - pinLength - gridSize)), str(int(pinTextSize)), FP.pins[currIdx - 1].actualGroup)
                        topX = distX
                        topY = distY
                    elif FP.pins[currIdx - 1].orientation == 'L':
                        if gSize > 1:
                            libTxt += 'T 0 {} {} {} 0 1 0 {} Normal 0 R C\n' \
                                .format(str(int(distX - pinLength - gridSize)), \
                                str(int(distY + (lastGroupSize + 1) * gridSize)), str(int(pinTextSize)), FP.pins[currIdx - 1].actualGroup)
                        rightX = distX
                        rightY = distY
                    elif FP.pins[currIdx - 1].orientation == 'R':
                        if gSize > 1:
                            libTxt += 'T 0 {} {} {} 0 1 0 {} Normal 0 L C\n' \
                                .format(str(int(distX + pinLength + gridSize)), \
                                str(int(distY + (lastGroupSize + 1) * gridSize)), str(int(pinTextSize)), FP.pins[currIdx - 1].actualGroup)
                        leftX = distX
                        leftY = distY
                        
                # set new coordinates
                gSize = FP.getGroupSize(pin.actualGroup)
                if pin.orientation == 'U':    # GND
                    distX = bottomX - yGroupOffset
                    distY = bottomY
                elif pin.orientation == 'D':  # VDD
                    distX = topX - yGroupOffset
                    distY = topY
                elif pin.orientation == 'L':
                    distX = rightX
                    distY = rightY + yGroupOffset
                elif pin.orientation == 'R':
                    distX = leftX
                    distY = leftY + yGroupOffset                      
                
            lastGroupTxtLen = 0
            lastGroupSize = 0
            lastGroupIdx = currIdx
            numGroups += 1
            # end if singleGroup  
        
        lastGroupSize += 1
            
        libTxt += 'X {} {} {} {} {} {} {} {} {} 1 {}\n' \
                    .format(pin.pinFunction + pin.addTxt, pin.pinID, str(distX), str(distY), \
                        str(pinLength), pin.orientation, str(pinTextSize), str(pinTextSize), str(FP.gUnitMapping.get(pin.actualGroup)), pin.symbol)
        if singleGroups:
            distY += yOffset
        else:
            if pin.orientation == 'U' or pin.orientation == 'D':
                distX -= yOffset
            elif pin.orientation == 'R' or pin.orientation == 'L':
                distY += yOffset
        lastGroup = pin.actualGroup
        if len(pin.pinFunction) + len(pin.addTxt) >= lastGroupTxtLen:
            lastGroupTxtLen = len(pin.pinFunction) + len(pin.addTxt)
        
        currIdx += 1
        # end while
        
    # last Rectangle
    if singleGroups and makeRec:
        libTxt += 'S {} {} {} {} {} 1 {} N\n' \
                    .format(str(distX + pinLength), str(int(distY - lastGroupSize * yOffset + gridSize)), \
                    str(int(distX + pinLength + lastGroupTxtLen * pinTextSize + gridSize)), \
                    str(int(distY)), str(FP.gUnitMapping.get(lastGroup)), int(pinTextSize / 5))
    if not singleGroups:
        libTxt += 'S {} {} {} {} 1 1 {} N\n' \
                    .format(str(int(leftX + pinLength)), str(int(topY - pinLength)), \
                    str(int(rightX - pinLength)), str(int(bottomY + pinLength)), int(pinTextSize / 5))
        
    libTxt += 'ENDDRAW\n' \
              'ENDDEF\n'    
        
    if singleGroups:
        devTxtOffsetX = 0
        devTxtOffsetY = 400
        devTxtAlign = 'L'
    if not singleGroups:
        devTxtOffsetX = 0
        devTxtOffsetY = 100
        devTxtAlign = 'C'
        
    libTxt = libTxt[:startPos] + '#\n' \
              '# {}_{}\n' \
              '#\n' \
              'DEF {}_{} U 0 40 Y Y {} L N\n' \
              'F0 \"U\" {} {} 60 H V {} CNN\n' \
              'F1 \"{}_{}\" {} {} 60 H V {} CNN\n' \
              'F2 \"{}\" {} {} 60 H V {} CIN\n' \
              'F3 \"~\" {} {} 60 H V {} CNN\n' \
              '$FPLIST\n' \
              ' {}\n' \
              '$ENDFPLIST\n' \
              'DRAW\n' \
                    .format(device, FP.name, \
                    device, FP.name, str(FP.gUnitMapping.get(FP.pinGroups[-1])), \
                    devTxtOffsetX, devTxtOffsetY, devTxtAlign, \
                    device, FP.name, devTxtOffsetX, devTxtOffsetY - 100, devTxtAlign, \
                    FP.name, devTxtOffsetX, devTxtOffsetY - 200, devTxtAlign, \
                    devTxtOffsetX, devTxtOffsetY - 300, devTxtAlign, \
                    '*BGA*') \
               + libTxt[startPos:]
    
    print '... done.', len(FP.pinGroups), 'pin groups and', len(FP.pins), 'pins found.' 
    FPID += 1
    #print FP.pinGroups
    # end for

if destNew:
    libTxt += '#\n' \
              '#End Library'
    dest.write(libTxt)
else:
    places = list(find_all(oldTxt, 'ENDDEF'))
    oldTxt = oldTxt[:places[-1] + 7] + libTxt + '\n' + oldTxt[places[-1] + 7:]
    dest.write(oldTxt)
    
dest.close()
print 'Export successful!'




















