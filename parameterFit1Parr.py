import os
import toolbox
import subprocess

verbose = False
saveIntermediateValues = True
NIter = 0

def computeFEData(p,modelsDir):
    files = os.listdir(modelsDir)
    files.sort()
    modelList = list()
    for modelScript in files:
        if (modelScript.endswith('.py')) and ('__init__' not in modelScript):
            modelList.append(modelScript)
    #if len(modelList)==1: raise Exception("This script is not really useful for only one script ")
    else:
        output = list()
        for model in modelList:
            out1job = runModel(p,model,modelsDir)
            output.append(out1job[0])
    return output,modelList

def runModel(p,modelScript,modelsDir):
    baseName = os.path.dirname(os.path.abspath(__file__))
    import sys
    sys.path.append(os.path.dirname(os.getcwd()))
    filePath = os.path.join(modelsDir,modelScript)
    workspace = toolbox.getWorkspace(filePath,baseName=baseName)
    if not(os.path.isdir(workspace)):
        try: os.makedirs(workspace)
        except WindowsError: print("file(s) probably locked!\n")
    # run abaqus analysis (function of parameters p) in workspace
    os.chdir(workspace)
    if verbose: print "running abaqus cae on %s"%(toolbox.getFileName(filePath))
    cmd = 'abaqus cae noGUI=%s'%(filePath)
    paramString = str(p)
    cmd += ' -- %s %s > %s 2>&1'%(str(baseName),paramString,'exeCalls.txt')
    if verbose: print 'cmd= ',cmd
    pCall1 = subprocess.call(cmd, shell=True)
    os.chdir(baseName)
    # run abaqus postPro -- this is the part where I did not find a way to work on a different workspace for each abaqus run
    cmd = 'abaqus python runAbaqus.py postPro %s'%(filePath)
    pCall2 = subprocess.call(cmd, shell=True)
    if pCall2:#the post pro function has not run properly
        writeErrorFile(workspace,modelScript,p,pCall1,pCall2)
        raise Exception("!! something has gone wrong, check notRun.txt")
        return 0
    else:
        feOutputFile = os.path.join(workspace,'output.ascii')
        with open(feOutputFile, 'r') as file:   
            output = zip(*(map(float,line.split()) for line in file))
        return output

def writeErrorFile(workspace,modelScript,p,pCall1,pCall2='not run yet'):
    feErrorFile = os.path.join(workspace,'notRun.txt')
    global NIter
    with open(feErrorFile, 'w') as file:
        file.write('running abaqus cae on %s returned %s\n'%(toolbox.getFileName(modelScript), pCall1))
        file.write('running post pro on %s returned %s\n'%(toolbox.getFileName(modelScript), pCall2))
        file.write('parameter inputs: %s\n'%(p))
        file.write('run number: %s\n'%(NIter))

def plotValues(fittedValues, modelScript, expData):
    baseName = os.path.dirname(os.path.abspath(__file__))
    workspace = toolbox.getWorkspace(modelScript,baseName)
    os.chdir(workspace)
    figFilePng = os.path.join(workspace,'fittedResults2.png')
    figFilePdf = os.path.join(workspace,'fittedResults2.pdf')
    import matplotlib.pyplot as plt
    plt.plot(expData[0],expData[1],'o',fittedValues[0],fittedValues[1],'x')
    plt.legend(['Data', 'Fit'])
    plt.title('Least-squares fit to data')
    plt.savefig(figFilePng, bbox_inches='tight')
    plt.savefig(figFilePdf, bbox_inches='tight')
    if not verbose:plt.show()
    return fittedValues

def saveValues(p, feData, names, value, no='final'):
    baseName = os.path.dirname(os.path.abspath(__file__))
    feDataFile = os.path.join(baseName,'verboseValues_%i.ascii'%no)
    with open(feDataFile, 'w') as file:
        file.write('run number: %s\n'%(no))
        file.write('parameter inputs: %s\n'%(p))
        file.write('least square error %s\n'%value)
        file.write('\n'.join('%s: %f ' %(name,data[0]) for data,name in zip(feData,names)))

def residuals(p, modelsDir, expDir):
    ''' residuals(p, expData) computes the diff (in a least square sense) between experimental data and FE data (function of p)
        p: set of parameters to optimize
        expDir: directory experimental data to fit
    '''
    # compute FE data function of parameters only - should return a 2D array (x,y) of floats
    # ---------------
    feData,modelNames = computeFEData(p,modelsDir)
    #
    import numpy as np
    diff = list()
    for data,name in zip(feData,modelNames):
        #read data file
        dataFile = os.path.join(expDir,name.split('.')[0]+'.ascii')
        with open(dataFile, 'r') as file: expData =  float(file.readline().split()[0])
        # add difference in list
        if data[0]: diff.append((expData - data[0])/expData)
    lstSq = 0
    for value in diff: lstSq+= value**2
    lstSq /= len(diff)
    lstSq = lstSq**0.5
    global NIter
    NIter += 1
    if saveIntermediateValues: saveValues(p, feData,modelNames, lstSq, NIter)
    return lstSq

def getOptiParam(modelsDir, expDir, optiParam, pBounds=None):
    global NIter
    from scipy.optimize import minimize_scalar
    opts = {'maxiter':optiParam['maxEval'],'disp':True}
    import numpy as np
    res = minimize_scalar(residuals, bounds=pBounds, args=(modelsDir, expDir), tol=optiParam['ftol'], method='bounded', options=opts)
    pLSQ = res.x
    fVal = res.fun
    d = {}
    d['funcalls']= res.nfev
    d['task']= res.message
    d['nIte']= NIter
    if verbose: print d
    return pLSQ,fVal,d

def main(expDir, modelsDir, options={}, pBounds=None):
    optiParam = {}
    optiParam['maxEval']=10
    optiParam['ftol']=1e-8
    optiParam.update(options)
    return getOptiParam(modelsDir, expDir, optiParam, pBounds)