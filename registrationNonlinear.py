import numpy as np
import scipy as sp
import tensorFieldUtils as tf
import nibabel as nib
import matplotlib.pyplot as plt
from scipy import ndimage
import registrationCommon as rcommon
from registrationCommon import const_prefilter_map_coordinates
import os
import sys
###############################################################
####### Non-linear Monomodal registration - EM (2D)############
###############################################################
def estimateNewMonomodalDeformationField2DLarge(moving, fixed, lambdaParam, maxOuterIter, previousDisplacement):
    '''
    Warning: in the monomodal case, the parameter lambda must be significantly lower than in the multimodal case. Try lambdaParam=1,
    as opposed as lambdaParam=150 used in the multimodal case
    '''
    innerTolerance=1e-4
    outerTolerance=1e-3
    sh=moving.shape
    X0,X1=np.mgrid[0:sh[0], 0:sh[1]]
    displacement     =np.zeros(shape=(moving.shape)+(2,), dtype=np.float64)
    residuals=np.zeros(shape=(moving.shape), dtype=np.float64)
    gradientField    =np.empty(shape=(moving.shape)+(2,), dtype=np.float64)
    totalDisplacement=np.zeros(shape=(moving.shape)+(2,), dtype=np.float64)
    if(previousDisplacement!=None):
        totalDisplacement[...]=previousDisplacement
    outerIter=0
    framesToCapture=5
    maxOuterIter=framesToCapture*((maxOuterIter+framesToCapture-1)/framesToCapture)
    itersPerCapture=maxOuterIter/framesToCapture
    plt.figure()
    while(outerIter<maxOuterIter):
        outerIter+=1
        print 'Outer iter:', outerIter
        warped=ndimage.map_coordinates(moving, [X0+totalDisplacement[...,0], X1+totalDisplacement[...,1]], prefilter=const_prefilter_map_coordinates)
        if((outerIter==1) or (outerIter%itersPerCapture==0)):
            plt.subplot(1,framesToCapture+1, 1+outerIter/itersPerCapture)
            rcommon.overlayImages(warped, fixed, False)
            plt.title('Iter:'+str(outerIter-1))
        sigmaField=np.ones_like(warped, dtype=np.float64)
        deltaField=fixed-warped
        g0, g1=sp.gradient(warped)
        gradientField[:,:,0]=g0
        gradientField[:,:,1]=g1
        maxVariation=1+innerTolerance
        innerIter=0
        maxResidual=0
        displacement[...]=0
        maxInnerIter=1000
        while((maxVariation>innerTolerance)and(innerIter<maxInnerIter)):
            innerIter+=1
            maxVariation=tf.iterateDisplacementField2DCYTHON(deltaField, sigmaField, gradientField,  lambdaParam, displacement, residuals)
            opt=np.max(residuals)
            if(maxResidual<opt):
                maxResidual=opt
        maxDisplacement=np.mean(np.abs(displacement))
        totalDisplacement+=displacement
        #totalDisplacement=tf.compose_vector_fields(displacement, totalDisplacement)
        if(maxDisplacement<outerTolerance):
            break
    print "Iter: ",innerIter, "Max lateral displacement:", maxDisplacement, "Max variation:",maxVariation, "Max residual:", maxResidual
    if(previousDisplacement!=None):
        return totalDisplacement-previousDisplacement
    return totalDisplacement


def estimateNewMonomodalDeformationField2D(moving, fixed, lambdaParam, maxIter, previousDisplacement):
    '''
    Warning: in the monomodal case, the parameter lambda must be significantly lower than in the multimodal case. Try lambdaParam=1,
    as opposed as lambdaParam=150 used in the multimodal case
    '''
    epsilon=1e-9
    sh=moving.shape
    X0,X1=np.mgrid[0:sh[0], 0:sh[1]]
    displacement     =np.zeros(shape=(moving.shape)+(2,), dtype=np.float64)
    residuals=np.zeros(shape=(moving.shape), dtype=np.float64)
    gradientField    =np.empty(shape=(moving.shape)+(2,), dtype=np.float64)
    totalDisplacement=np.zeros(shape=(moving.shape)+(2,), dtype=np.float64)
    warped=None
    if(previousDisplacement!=None):
        totalDisplacement[...]=previousDisplacement
        warped=ndimage.map_coordinates(moving, [X0+totalDisplacement[...,0], X1+totalDisplacement[...,1]], prefilter=const_prefilter_map_coordinates)
    else:
        warped=moving
    sigmaField=np.ones_like(warped, dtype=np.float64)
    deltaField=fixed-warped
    g0, g1=sp.gradient(warped)
    gradientField[:,:,0]=g0
    gradientField[:,:,1]=g1
    maxVariation=1+epsilon
    innerIter=0
    maxResidual=0
    while((maxVariation>epsilon)and(innerIter<maxIter)):
        innerIter+=1
        maxVariation=tf.iterateDisplacementField2DCYTHON(deltaField, sigmaField, gradientField,  lambdaParam, displacement, residuals)
        opt=np.max(residuals)
        if(maxResidual<opt):
            maxResidual=opt
    maxDisplacement=np.max(np.abs(displacement))
    print "Iter: ",innerIter, "Max lateral displacement:", maxDisplacement, "Max variation:",maxVariation, "Max residual:", maxResidual
    return displacement

def estimateMonomodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, level, displacementList):
    n=len(movingPyramid)
    if(level==(n-1)):
        displacement=estimateNewMonomodalDeformationField2DLarge(movingPyramid[level], fixedPyramid[level], lambdaParam, maxOuterIter[level], None)
        if(displacementList!=None):
            displacementList.insert(0,displacement)
        return displacement
    subDisplacement=estimateMonomodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, level+1, displacementList)
    sh=movingPyramid[level].shape
    X0,X1=np.mgrid[0:sh[0], 0:sh[1]]*0.5
    upsampled=np.empty(shape=(movingPyramid[level].shape)+(2,), dtype=np.float64)
    upsampled[:,:,0]=ndimage.map_coordinates(subDisplacement[:,:,0], [X0, X1], prefilter=const_prefilter_map_coordinates)*2
    upsampled[:,:,1]=ndimage.map_coordinates(subDisplacement[:,:,1], [X0, X1], prefilter=const_prefilter_map_coordinates)*2
    newDisplacement=estimateNewMonomodalDeformationField2DLarge(movingPyramid[level], fixedPyramid[level], lambdaParam, maxOuterIter[level], upsampled)
    newDisplacement+=upsampled
    if(displacementList!=None):
        displacementList.insert(0, newDisplacement)
    return newDisplacement

def testEstimateMonomodalDeformationField2DMultiScale(lambdaParam):
    fname0='IBSR_01_to_02.nii.gz'
    fname1='data/t1/IBSR18/IBSR_02/IBSR_02_ana_strip.nii.gz'
    nib_moving = nib.load(fname0)
    nib_fixed= nib.load(fname1)
    moving=nib_moving.get_data().squeeze()
    fixed=nib_fixed.get_data().squeeze()
    moving=np.copy(moving, order='C')
    fixed=np.copy(fixed, order='C')
    sl=moving.shape
    sr=fixed.shape
    level=5
    #---sagital---
    moving=moving[sl[0]//2,:,:].copy()
    fixed=fixed[sr[0]//2,:,:].copy()
    #---coronal---
    #moving=moving[:,sl[1]//2,:].copy()
    #fixed=fixed[:,sr[1]//2,:].copy()
    #---axial---
    #moving=moving[:,:,sl[2]//2].copy()
    #fixed=fixed[:,:,sr[2]//2].copy()
    maskMoving=moving>0
    maskFixed=fixed>0
    movingPyramid=[img for img in rcommon.pyramid_gaussian_2D(moving, level, maskMoving)]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_2D(fixed, level, maskFixed)]
    rcommon.plotOverlaidPyramids(movingPyramid, fixedPyramid)
    displacementList=[]
    maxIter=200
    displacement=estimateMonomodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxIter, 0,displacementList)
    warpPyramid=[rcommon.warpImage(movingPyramid[i], displacementList[i]) for i in range(level+1)]
    rcommon.plotOverlaidPyramids(warpPyramid, fixedPyramid)
    rcommon.overlayImages(warpPyramid[0], fixedPyramid[0])
    rcommon.plotDeformationField(displacement)
    nrm=np.sqrt(displacement[...,0]**2 + displacement[...,1]**2)
    maxNorm=np.max(nrm)
    displacement[...,0]*=(maskMoving + maskFixed)
    displacement[...,1]*=(maskMoving + maskFixed)
    rcommon.plotDeformationField(displacement)
    #nrm=np.sqrt(displacement[...,0]**2 + displacement[...,1]**2)
    #plt.figure()
    #plt.imshow(nrm)
    print 'Max global displacement: ', maxNorm

def testCircleToCMonomodal(lambdaParam, maxOuterIter):
    fname0='data/circle.png'
    #fname0='data/C_trans.png'
    fname1='data/C.png'
    nib_moving=plt.imread(fname0)
    nib_fixed=plt.imread(fname1)
    moving=nib_moving[:,:,0]
    fixed=nib_fixed[:,:,1]
    moving=(moving-moving.min())/(moving.max() - moving.min())
    fixed=(fixed-fixed.min())/(fixed.max() - fixed.min())
    level=3
    maskMoving=moving>0
    maskFixed=fixed>0
    movingPyramid=[img for img in rcommon.pyramid_gaussian_2D(moving, level, maskMoving)]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_2D(fixed, level, maskFixed)]
    rcommon.plotOverlaidPyramids(movingPyramid, fixedPyramid)
    displacementList=[]
    displacement=estimateMonomodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, 0,displacementList)
    inverse=tf.invert_vector_field(displacement, 1, 100, 1e-7)
    residual=tf.compose_vector_fields(displacement, inverse)
    warpPyramid=[rcommon.warpImage(movingPyramid[i], displacementList[i]) for i in range(level+1)]
    rcommon.plotOverlaidPyramids(warpPyramid, fixedPyramid)
    rcommon.overlayImages(warpPyramid[0], fixedPyramid[0])
    rcommon.plotDiffeomorphism(displacement, inverse, residual, 7)
###############################################################
####### Non-linear Monomodal registration - EM (3D)############
###############################################################

def estimateNewMonomodalDeformationField3D(moving, fixed, lambdaParam, maxIter, previousDisplacement=None):
    epsilon=1e-3
    sh=moving.shape
    X0,X1,X2=np.mgrid[0:sh[0], 0:sh[1], 0:sh[2]]
    displacement     =np.zeros(shape=(moving.shape)+(3,), dtype=np.float64)
    residuals        =np.zeros(shape=(moving.shape), dtype=np.float64)
    gradientField    =np.empty(shape=(moving.shape)+(3,), dtype=np.float64)
    totalDisplacement=np.zeros(shape=(moving.shape)+(3,), dtype=np.float64)
    if(previousDisplacement!=None):
        totalDisplacement[...]=previousDisplacement
    warped=ndimage.map_coordinates(moving, [X0+totalDisplacement[...,0], X1+totalDisplacement[...,1], X2+totalDisplacement[...,2]], prefilter=const_prefilter_map_coordinates)
    sigmaField=np.ones_like(warped, dtype=np.float64)
    deltaField=fixed-warped
    g0, g1, g2=sp.gradient(warped)
    gradientField[:,:,:,0]=g0
    gradientField[:,:,:,1]=g1
    gradientField[:,:,:,2]=g2
    maxVariation=1+epsilon
    innerIter=0
    maxResidual=0
    while((maxVariation>epsilon)and(innerIter<maxIter)):
        innerIter+=1
        if(innerIter%100==0):
            print "Iterations:",innerIter, ". Max variation:", maxVariation
        maxVariation=tf.iterateDisplacementField3DCYTHON(deltaField, sigmaField, gradientField,  lambdaParam, totalDisplacement, displacement, residuals)
        opt=np.max(residuals)
        if(maxResidual<opt):
            maxResidual=opt
    maxDisplacement=np.max(np.abs(displacement))
    print "Iter: ",innerIter, "Max lateral displacement:", maxDisplacement, "Max variation:",maxVariation, "Max residual:", maxResidual
    return displacement

def estimateMonomodalDeformationField3DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, level=0, displacementList=None):
    n=len(movingPyramid)
    if(level==(n-1)):
        displacement=estimateNewMonomodalDeformationField3D(movingPyramid[level], fixedPyramid[level], lambdaParam, maxOuterIter[level], None)
        if(displacementList!=None):
            displacementList.insert(0,displacement)
        return displacement
    subDisplacement=estimateMonomodalDeformationField3DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, level+1, displacementList)
    sh=movingPyramid[level].shape
    X0,X1,X2=np.mgrid[0:sh[0], 0:sh[1], 0:sh[2]]*0.5
    upsampled=np.empty(shape=(movingPyramid[level].shape)+(3,), dtype=np.float64)
    upsampled[:,:,:,0]=ndimage.map_coordinates(subDisplacement[:,:,:,0], [X0, X1, X2], prefilter=const_prefilter_map_coordinates)*2
    upsampled[:,:,:,1]=ndimage.map_coordinates(subDisplacement[:,:,:,1], [X0, X1, X2], prefilter=const_prefilter_map_coordinates)*2
    upsampled[:,:,:,2]=ndimage.map_coordinates(subDisplacement[:,:,:,2], [X0, X1, X2], prefilter=const_prefilter_map_coordinates)*2
    newDisplacement=estimateNewMonomodalDeformationField3D(movingPyramid[level], fixedPyramid[level], lambdaParam, maxOuterIter[level], upsampled)
    newDisplacement+=upsampled
    if(displacementList!=None):
        displacementList.insert(0, newDisplacement)
    return newDisplacement

def registerNonlinearMonomodal3D(moving, fixed, lambdaParam, levels):
    maskMoving=moving>0
    maskFixed=fixed>0
    movingPyramid=[img for img in rcommon.pyramid_gaussian_3D(moving, levels, maskMoving)]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_3D(fixed, levels, maskFixed)]
    maxOuterIter=[10,50,100,100,100,100,100,100,100]
    displacement=estimateMonomodalDeformationField3DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, 0, None)
    warped=rcommon.warpVolume(movingPyramid[0], displacement)
    return displacement, warped


def displayRegistrationResult():
    fnameMoving='data/affineRegistered/templateT1ToIBSR01T1.nii.gz'
    fnameFixed='data/t1/IBSR18/IBSR_01/IBSR_01_ana_strip.nii.gz'
    nib_fixed = nib.load(fnameFixed)
    fixed=nib_fixed.get_data().squeeze()
    fixed=np.copy(fixed, order='C')
    nib_moving = nib.load(fnameMoving)
    moving=nib_moving.get_data().squeeze()
    moving=np.copy(moving, order='C')
    fnameDisplacement='displacement_templateT1ToIBSR01T1.npy'
    fnameWarped='warped_templateT1ToIBSR01T1.npy'
    displacement=np.load(fnameDisplacement)
    warped=np.load(fnameWarped)
    sh=moving.shape
    shown=warped
    f=rcommon.overlayImages(shown[:,sh[1]//4,:], fixed[:,sh[1]//4,:])
    f=rcommon.overlayImages(shown[:,sh[1]//2,:], fixed[:,sh[1]//2,:])
    f=rcommon.overlayImages(shown[:,3*sh[1]//4,:], fixed[:,3*sh[1]//4,:])
    f=rcommon.overlayImages(shown[sh[0]//4,:,:], fixed[sh[0]//4,:,:])
    f=rcommon.overlayImages(shown[sh[0]//2,:,:], fixed[sh[0]//2,:,:])
    f=rcommon.overlayImages(shown[3*sh[0]//4,:,:], fixed[3*sh[0]//4,:,:])
    f=rcommon.overlayImages(shown[:,:,sh[2]//4], fixed[:,:,sh[2]//4])
    f=rcommon.overlayImages(shown[:,:,sh[2]//2], fixed[:,:,sh[2]//2])
    f=rcommon.overlayImages(shown[:,:,3*sh[2]//4], fixed[:,:,3*sh[2]//4])

def testEstimateMonomodalDeformationField3DMultiScale(lambdaParam):
    #fname0='IBSR_01_to_02.nii.gz'
    #fname1='data/t1/IBSR18/IBSR_02/IBSR_02_ana_strip.nii.gz'
    fnameMoving='data/affineRegistered/templateT1ToIBSR01T1.nii.gz'
    fnameFixed='data/t1/IBSR18/IBSR_01/IBSR_01_ana_strip.nii.gz'
    nib_moving = nib.load(fnameMoving)
    nib_fixed = nib.load(fnameFixed)
    moving=nib_moving.get_data().squeeze().astype(np.float64)
    fixed=nib_fixed.get_data().squeeze().astype(np.float64)
    moving=np.copy(moving, order='C')
    moving=(moving-moving.min())/(moving.max()-moving.min())
    fixed=(fixed-fixed.min())/(fixed.max()-fixed.min())
    fixed=np.copy(fixed, order='C')
    level=3
    maskMoving=moving>0
    maskFixed=fixed>0
    movingPyramid=[img for img in rcommon.pyramid_gaussian_3D(moving, level, maskMoving)]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_3D(fixed, level, maskFixed)]
    rcommon.plotOverlaidPyramids3DCoronal(movingPyramid, fixedPyramid)
    maxOuterIter=[100,100,100,100,100,100,100,100,100]
    displacementList=[]
    displacement=estimateMonomodalDeformationField3DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, 0,displacementList)
    warpPyramid=[rcommon.warpVolume(movingPyramid[i], displacementList[i]) for i in range(level+1)]
    ####save results###
    np.save('displacement_templateT1ToIBSR01T1.npy', displacement)
    np.save('warped_templateT1ToIBSR01T1.npy', warpPyramid[0])
    ###################
    sh=movingPyramid[0].shape
    rcommon.overlayImages(warpPyramid[0][:,sh[1]//4,:], fixedPyramid[0][:,sh[1]//4,:])
    rcommon.overlayImages(warpPyramid[0][:,sh[1]//2,:], fixedPyramid[0][:,sh[1]//2,:])
    rcommon.overlayImages(warpPyramid[0][:,3*sh[1]//4,:], fixedPyramid[0][:,3*sh[1]//4,:])
    rcommon.overlayImages(warpPyramid[0][sh[0]//4,:,:], fixedPyramid[0][sh[0]//4,:,:])
    rcommon.overlayImages(warpPyramid[0][sh[0]//2,:,:], fixedPyramid[0][sh[0]//2,:,:])
    rcommon.overlayImages(warpPyramid[0][3*sh[0]//4,:,:], fixedPyramid[0][3*sh[0]//4,:,:])
    rcommon.overlayImages(warpPyramid[0][:,:,sh[2]//4], fixedPyramid[0][:,:,sh[2]//4])
    rcommon.overlayImages(warpPyramid[0][:,:,sh[2]//2], fixedPyramid[0][:,:,sh[2]//2])
    rcommon.overlayImages(warpPyramid[0][:,:,3*sh[2]//4], fixedPyramid[0][:,:,3*sh[2]//4])
    #rcommon.plotDeformationField(displacement)
    nrm=np.sqrt(displacement[...,0]**2 + displacement[...,1]**2 + displacement[...,2]**2)
    maxNorm=np.max(nrm)
    #displacement[...,0]*=(maskMoving + maskFixed)
    #displacement[...,1]*=(maskMoving + maskFixed)
    #rcommon.plotDeformationField(displacement)
    #figure()
    #imshow(nrm[:,sh[1]//2,:])
    print 'Max global displacement: ', maxNorm

###############################################################
####### Non-linear Multimodal registration - EM (2D)###########
###############################################################
def estimateNewMultimodalDeformationField2D(moving, fixed, lambdaDisplacement, quantizationLevels, maxOuterIter, previousDisplacement):
    innerTolerance=1e-4
    outerTolerance=1e-3
    sh=moving.shape
    X0,X1=np.mgrid[0:sh[0], 0:sh[1]]
    displacement     =np.empty(shape=(moving.shape)+(2,), dtype=np.float64)
    residuals=np.zeros(shape=(moving.shape), dtype=np.float64)
    gradientField    =np.empty(shape=(moving.shape)+(2,), dtype=np.float64)
    totalDisplacement=np.zeros(shape=(moving.shape)+(2,), dtype=np.float64)
    if(previousDisplacement!=None):
        totalDisplacement[...]=previousDisplacement
    fixedQ=None
    grayLevels=None
    fixedQ, grayLevels, hist=tf.quantizePositiveImageCYTHON(fixed, quantizationLevels)
    fixedQ=np.array(fixedQ, dtype=np.int32)
    finished=False
    outerIter=0
    maxDisplacement=None
    maxVariation=None
    maxResidual=0
    while((not finished) and (outerIter<maxOuterIter)):
        outerIter+=1
        #---E step---
        warped=ndimage.map_coordinates(moving, [X0+totalDisplacement[...,0], X1+totalDisplacement[...,1]], prefilter=True)
        movingMask=((moving>0)*1.0)*((fixed>0)*1.0)
        warpedMovingMask=ndimage.map_coordinates(movingMask, [X0+totalDisplacement[...,0], X1+totalDisplacement[...,1]], order=0, prefilter=False)
        warpedMovingMask=warpedMovingMask.astype(np.int32)
        #means, variances=tf.computeMaskedImageClassStatsCYTHON(warpedMovingMask, warped, quantizationLevels, fixedQ)
        means, variances=tf.computeMaskedImageClassStatsCYTHON(warpedMovingMask, warped, quantizationLevels, fixedQ)            
        means[0]=0
        means=np.array(means)
        variances=np.array(variances)
        sigmaField=variances[fixedQ]
        deltaField=means[fixedQ]-warped#########Delta-field using Arce's rule
        #--M step--
        g0, g1=sp.gradient(warped)
        gradientField[:,:,0]=g0
        gradientField[:,:,1]=g1
        maxVariation=1+innerTolerance
        innerIter=0
        maxInnerIter=1000
        displacement[...]=0
        while((maxVariation>innerTolerance)and(innerIter<maxInnerIter)):
            innerIter+=1
            maxVariation=tf.iterateDisplacementField2DCYTHON(deltaField, sigmaField, gradientField,  lambdaDisplacement, displacement, residuals)
            opt=np.max(residuals)
            if(maxResidual<opt):
                maxResidual=opt
        #--accumulate displacement--
        totalDisplacement+=displacement
        #--check stop condition--
        nrm=np.sqrt(displacement[...,0]**2+displacement[...,1]**2)
        maxDisplacement=np.mean(nrm)
        if((maxDisplacement<outerTolerance)or(outerIter>=maxOuterIter)):
            finished=True
            plt.figure()
            plt.subplot(1,3,1)
            plt.imshow(means[fixedQ],cmap=plt.cm.gray)    
            plt.title("Estimated warped modality")
            plt.subplot(1,3,2)
#            plt.imshow(warpedMovingMask,cmap=plt.cm.gray)
#            plt.title("Warped mask")
#            plt.imshow(warped,cmap=plt.cm.gray)
#            plt.title("Warped")
            plt.imshow(fixedQ,cmap=plt.cm.gray)
            plt.title("Quantized")
            plt.subplot(1,3,3)
            plt.plot(means)
            plt.title("Means")
    print "Iter: ",outerIter, "Mean displacement:", maxDisplacement, "Max variation:",maxVariation, "Max residual:", maxResidual
    if(previousDisplacement!=None):
        return totalDisplacement-previousDisplacement
    return totalDisplacement

def estimateMultimodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, level=0, displacementList=None):
    n=len(movingPyramid)
    quantizationLevels=256
    if(level==(n-1)):
        displacement=estimateNewMultimodalDeformationField2D(movingPyramid[level], fixedPyramid[level], lambdaParam, quantizationLevels, maxOuterIter[level], None)
        if(displacementList!=None):
            displacementList.insert(0,displacement)
        return displacement
    subDisplacement=estimateMultimodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, level+1, displacementList)
    sh=movingPyramid[level].shape
    X0,X1=np.mgrid[0:sh[0], 0:sh[1]]*0.5
    upsampled=np.empty(shape=(movingPyramid[level].shape)+(2,), dtype=np.float64)
    upsampled[:,:,0]=ndimage.map_coordinates(subDisplacement[:,:,0], [X0, X1], prefilter=const_prefilter_map_coordinates)*2
    upsampled[:,:,1]=ndimage.map_coordinates(subDisplacement[:,:,1], [X0, X1], prefilter=const_prefilter_map_coordinates)*2
    newDisplacement=estimateNewMultimodalDeformationField2D(movingPyramid[level], fixedPyramid[level], lambdaParam, quantizationLevels, maxOuterIter[level], upsampled)
    newDisplacement+=upsampled
    if(displacementList!=None):
        displacementList.insert(0, newDisplacement)
    return newDisplacement

def registerNonlinearMultimodal2D(moving, fixed, lambdaParam, levels):
    maskMoving=moving>0
    maskFixed=fixed>0
    movingPyramid=[img for img in rcommon.pyramid_gaussian_3D(moving, levels, maskMoving)]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_3D(fixed, levels, maskFixed)]
    maxOuterIter=[10,50,100,100,100,100]
    displacement=estimateMultimodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, 0, None, False)
    warped=rcommon.warpVolume(movingPyramid[0], displacement)
    return displacement, warped

def testEstimateMultimodalDeformationField2DMultiScale(lambdaParam, synthetic):
    #fname0='IBSR_01_to_02.nii.gz'
    #fname1='data/t1/IBSR18/IBSR_02/IBSR_02_ana_strip.nii.gz'
    displacementGTName='templateToIBSR01_GT.npy'
    fnameMoving='data/t2/IBSR_t2template_to_01.nii.gz'
    fnameFixed='data/t1/IBSR_template_to_01.nii.gz'
    nib_moving = nib.load(fnameMoving)
    nib_fixed = nib.load(fnameFixed)
    moving=nib_moving.get_data().squeeze().astype(np.float64)
    fixed=nib_fixed.get_data().squeeze().astype(np.float64)
    moving=np.copy(moving, order='C')
    fixed=np.copy(fixed, order='C')
    sl=moving.shape
    sr=fixed.shape    
    moving=moving[:,sl[1]//2,:].copy()
    fixed=fixed[:,sr[1]//2,:].copy()
    moving=(moving-moving.min())/(moving.max()-moving.min())
    fixed=(fixed-fixed.min())/(fixed.max()-fixed.min())
    maxOuterIter=[10,50,100,100,100,100]
    if(synthetic):
        print 'Generating synthetic field...'
        #----apply synthetic deformation field to fixed image
        GT=rcommon.createDeformationField2D_type2(fixed.shape[0], fixed.shape[1], 8)
        rcommon.plotDiffeomorphism(GT, GT, GT, 'inv-direct', 7)
        warpedFixed=rcommon.warpImage(fixed,GT)
    else:
        templateT1=nib.load('data/t1/IBSR_template_to_01.nii.gz')
        templateT1=templateT1.get_data().squeeze().astype(np.float64)
        templateT1=np.copy(templateT1, order='C')
        sh=templateT1.shape
        templateT1=templateT1[:,sh[1]//2,:]
        templateT1=(templateT1-templateT1.min())/(templateT1.max()-templateT1.min())
        if(os.path.exists(displacementGTName)):
            print 'Loading precomputed realistic field...'
            GT=np.load(displacementGTName)
        else:
            print 'Generating realistic field...'
            #load two T1 images: the template and an IBSR sample
            ibsrT1=nib.load('data/t1/IBSR18/IBSR_01/IBSR_01_ana_strip.nii.gz')
            ibsrT1=ibsrT1.get_data().squeeze().astype(np.float64)
            ibsrT1=np.copy(ibsrT1, order='C')
            ibsrT1=ibsrT1[:,sh[1]//2,:]
            ibsrT1=(ibsrT1-ibsrT1.min())/(ibsrT1.max()-ibsrT1.min())
            #register the template(moving) to the ibsr sample(fixed)
            maskMoving=templateT1>0
            maskFixed=ibsrT1>0
            movingPyramid=[img for img in rcommon.pyramid_gaussian_2D(templateT1, 3, maskMoving)]
            fixedPyramid=[img for img in rcommon.pyramid_gaussian_2D(ibsrT1, 3, maskFixed)]
            #----apply 'realistic' deformation field to fixed image
            GT=estimateMultimodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, 0, None)
            np.save(displacementGTName, GT)
        warpedFixed=rcommon.warpImage(templateT1, GT)
    print 'Registering T2 (template) to deformed T1 (template)...'
    level=3
    maskMoving=moving>0
    maskFixed=warpedFixed>0
#    movingPyramid=[img for img in rcommon.pyramid_gaussian_2D(moving, level, maskMoving)]
#    fixedPyramid=[img for img in rcommon.pyramid_gaussian_2D(warpedFixed, level, maskFixed)]
    movingPyramid=[img for img in rcommon.pyramid_gaussian_2D(moving, level, np.ones_like(maskMoving))]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_2D(warpedFixed, level, np.ones_like(maskFixed))]
    plt.figure()
    plt.subplot(1,2,1)
    plt.imshow(moving, cmap=plt.cm.gray)
    plt.title('Moving')
    plt.subplot(1,2,2)
    plt.imshow(warpedFixed, cmap=plt.cm.gray)
    plt.title('Fixed')
    rcommon.plotOverlaidPyramids(movingPyramid, fixedPyramid)
    displacementList=[]
    displacement=estimateMultimodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, 0, displacementList)
    rcommon.plotDiffeomorphism(displacement, displacement, displacement, 'inv-direct', 7)
    warpPyramid=[rcommon.warpImage(movingPyramid[i], displacementList[i]) for i in range(level+1)]
    rcommon.plotOverlaidPyramids(warpPyramid, fixedPyramid)
    rcommon.overlayImages(warpPyramid[0], fixedPyramid[0])
    rcommon.plotDeformationField(displacement)
    displacement[...,0]*=(maskFixed)
    displacement[...,1]*=(maskFixed)
    nrm=np.sqrt(displacement[...,0]**2 + displacement[...,1]**2)
    nrm*=maskFixed
    maxNorm=np.max(nrm)
    rcommon.plotDeformationField(displacement)
    residual=((displacement-GT))**2
    meanDisplacementError=np.sqrt(residual.sum(2)*(maskFixed)).mean()
    stdevDisplacementError=np.sqrt(residual.sum(2)*(maskFixed)).std()
    
    print 'Max global displacement: ', maxNorm
    print 'Mean displacement error: ', meanDisplacementError,'(',stdevDisplacementError,')'

def testCircleToCMultimodal(lambdaParam):
    fnameMoving='data/circle.png'
    #fnameMoving='data/C_trans.png'
    fnameFixed='data/C.png'
    nib_moving=plt.imread(fnameMoving)
    nib_fixed=plt.imread(fnameFixed)
    moving=nib_moving[:,:,0]
    fixed=nib_fixed[:,:,1]
    level=2
    maskMoving=moving>0
    maskFixed=fixed>0
    movingPyramid=[img for img in rcommon.pyramid_gaussian_2D(moving, level, maskMoving)]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_2D(fixed, level, maskFixed)]
    rcommon.plotOverlaidPyramids(movingPyramid, fixedPyramid)
    displacementList=[]
    maxOuterIter=[10,50,100,100,100,100]
    displacement=estimateMultimodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, 0,displacementList)
    warpPyramid=[rcommon.warpImage(movingPyramid[i], displacementList[i]) for i in range(level+1)]
    rcommon.plotOverlaidPyramids(warpPyramid, fixedPyramid)
    rcommon.overlayImages(warpPyramid[0], fixedPyramid[0])
    rcommon.plotDeformedLattice(displacement)


###############################################################
####### Non-linear Multimodal registration - EM (3D)###########
###############################################################
def estimateNewMultimodalNonlinearField3D(moving, fixed, initAffine, lambdaDisplacement, quantizationLevels, maxOuterIter, previousDisplacement, reportProgress=False):
    innerTolerance=1e-3
    outerTolerance=1e-3
    displacement     =np.empty(shape=(fixed.shape)+(3,), dtype=np.float64)
    residuals=np.zeros(shape=(fixed.shape), dtype=np.float64)
    gradientField    =np.empty(shape=(fixed.shape)+(3,), dtype=np.float64)
    totalDisplacement=np.zeros(shape=(fixed.shape)+(3,), dtype=np.float64)
    if(previousDisplacement!=None):
        totalDisplacement[...]=previousDisplacement
    fixedQ=None
    grayLevels=None
    fixedQ, grayLevels, hist=tf.quantizePositiveVolumeCYTHON(fixed, quantizationLevels)
    fixedQ=np.array(fixedQ, dtype=np.int32)
    finished=False
    outerIter=0
    maxDisplacement=None
    maxVariation=None
    maxResidual=0
    fixedMask=(fixed>0).astype(np.int32)
    movingMask=(moving>0).astype(np.int32)
    trustRegion=fixedMask*np.array(tf.warp_discrete_volumeNNAffine(movingMask, np.array(fixedMask.shape, dtype=np.int32), initAffine))#consider only the overlap after affine registration
    while((not finished) and (outerIter<maxOuterIter)):
        outerIter+=1
        if(reportProgress):
            print 'Iter:',outerIter,'/',maxOuterIter
        #---E step---
        warped=np.array(tf.warp_volume(moving, totalDisplacement, initAffine))
        warpedMask=np.array(tf.warp_discrete_volumeNN(trustRegion, totalDisplacement, np.eye(4))).astype(np.int32)#the affine mapping was already applied
        means, variances=tf.computeMaskedVolumeClassStatsCYTHON(warpedMask, warped, quantizationLevels, fixedQ)        
        means[0]=0
        means=np.array(means)
        variances=np.array(variances)
        sigmaField=variances[fixedQ]
        deltaField=means[fixedQ]-warped#########Delta-field using Arce's rule
        #--M step--
        g0, g1, g2=sp.gradient(warped)
        gradientField[:,:,:,0]=g0
        gradientField[:,:,:,1]=g1
        gradientField[:,:,:,2]=g2
        maxVariation=1+innerTolerance
        innerIter=0
        maxInnerIter=100
        displacement[...]=0
        while((maxVariation>innerTolerance)and(innerIter<maxInnerIter)):
            innerIter+=1
            maxVariation=tf.iterateDisplacementField3DCYTHON(deltaField, sigmaField, gradientField,  lambdaDisplacement, totalDisplacement, displacement, residuals)
            opt=np.max(residuals)
            if(maxResidual<opt):
                maxResidual=opt
        #--accumulate displacement--
        totalDisplacement+=displacement
        #--check stop condition--
        nrm=np.sqrt(displacement[...,0]**2+displacement[...,1]**2+displacement[...,2]**2)
        maxDisplacement=np.mean(nrm)
        if((maxDisplacement<outerTolerance)or(outerIter>=maxOuterIter)):
            finished=True
    print "Iter: ",outerIter, "Mean displacement:", maxDisplacement, "Max variation:",maxVariation, "Max residual:", maxResidual
    if(previousDisplacement!=None):
        return totalDisplacement-previousDisplacement
    return totalDisplacement

def estimateMultimodalNonlinearField3DMultiScale(movingPyramid, fixedPyramid, initAffine, lambdaParam, maxOuterIter, level=0, displacementList=None):
    n=len(movingPyramid)
    quantizationLevels=256
    if(level==(n-1)):
        displacement=estimateNewMultimodalNonlinearField3D(movingPyramid[level], fixedPyramid[level], initAffine, lambdaParam, quantizationLevels, maxOuterIter[level], None, level==0)
        if(displacementList!=None):
            displacementList.insert(0, displacement)
        return displacement
    subAffine=initAffine.copy()
    subAffine[:3,3]*=0.5
    subDisplacement=estimateMultimodalNonlinearField3DMultiScale(movingPyramid, fixedPyramid, subAffine, lambdaParam, maxOuterIter, level+1, displacementList)
    sh=np.array(fixedPyramid[level].shape).astype(np.int32)
    upsampled=np.array(tf.upsample_displacement_field3D(subDisplacement, sh))*2
    newDisplacement=estimateNewMultimodalNonlinearField3D(movingPyramid[level], fixedPyramid[level], initAffine, lambdaParam, quantizationLevels, maxOuterIter[level], upsampled, level==0)
    newDisplacement+=upsampled
    if(displacementList!=None):
        displacementList.insert(0, newDisplacement)
    return newDisplacement

def saveDeformedLattice3D(displacement, oname):
    minVal, maxVal=tf.get_displacement_range(displacement, None)
    sh=np.array([np.ceil(maxVal[0]),np.ceil(maxVal[1]),np.ceil(maxVal[2])], dtype=np.int32)
    L=np.array(rcommon.drawLattice3D(sh, 10))
    warped=np.array(tf.warp_volume(L, displacement, np.eye(4))).astype(np.int16)
    img=nib.Nifti1Image(warped, np.eye(4))
    img.to_filename(oname)

def testEstimateMultimodalNonlinearField3DMultiScale(fnameMoving, fnameFixed, fnameAffine, warpDir, lambdaParam):
    '''
        testEstimateMultimodalDiffeomorphicField3DMultiScale('IBSR_01_ana_strip.nii.gz', 't1_icbm_normal_1mm_pn0_rf0_peeled.nii.gz', 'IBSR_01_ana_strip_t1_icbm_normal_1mm_pn0_rf0_peeledAffine.txt', 100)
    '''
    print 'Registering', fnameMoving, 'to', fnameFixed,'with lambda=',lambdaParam  
    sys.stdout.flush()
    moving = nib.load(fnameMoving)
    fixed= nib.load(fnameFixed)
    referenceShape=np.array(fixed.shape, dtype=np.int32)
    M=moving.get_affine()
    F=fixed.get_affine()
    if not fnameAffine:
        T=np.eye(4)
    else:
        T=rcommon.readAntsAffine(fnameAffine)
    initAffine=np.linalg.inv(M).dot(T.dot(F))
    print initAffine
    moving=moving.get_data().squeeze().astype(np.float64)
    fixed=fixed.get_data().squeeze().astype(np.float64)
    moving=np.copy(moving, order='C')
    fixed=np.copy(fixed, order='C')
    moving=(moving-moving.min())/(moving.max()-moving.min())
    fixed=(fixed-fixed.min())/(fixed.max()-fixed.min())
    level=2
    maskMoving=moving>0
    maskFixed=fixed>0
    movingPyramid=[img for img in rcommon.pyramid_gaussian_3D(moving, level, maskMoving)]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_3D(fixed, level, maskFixed)]
    maxOuterIter=[25,50,100,100, 100, 100]
    baseMoving=rcommon.getBaseFileName(fnameMoving)
    baseFixed=rcommon.getBaseFileName(fnameFixed)    
    displacement=estimateMultimodalNonlinearField3DMultiScale(movingPyramid, fixedPyramid, initAffine, lambdaParam, maxOuterIter, 0,None)
    tf.prepend_affine_to_displacement_field(displacement, initAffine)
    #####Warp all requested volumes
    #---first the target using tri-linear interpolation---
    moving=nib.load(fnameMoving).get_data().squeeze().astype(np.float64)
    moving=np.copy(moving, order='C')
    warped=np.array(tf.warp_volume(moving, displacement)).astype(np.int16)
    imgWarped=nib.Nifti1Image(warped, F)
    imgWarped.to_filename('warpedDiff_'+baseMoving+'_'+baseFixed+'.nii.gz')
    #---warp using affine only
    moving=nib.load(fnameMoving).get_data().squeeze().astype(np.int32)
    moving=np.copy(moving, order='C')
    warped=np.array(tf.warp_discrete_volumeNNAffine(moving, referenceShape, initAffine)).astype(np.int16)
    imgWarped=nib.Nifti1Image(warped, F)#The affine transformation is the reference's one
    imgWarped.to_filename('warpedAffine_'+baseMoving+'_'+baseFixed+'.nii.gz')
    #---now the rest of the targets using nearest neighbor
    names=[os.path.join(warpDir,name) for name in os.listdir(warpDir)]
    for name in names:
        #---warp using the non-linear deformation
        toWarp=nib.load(name).get_data().squeeze().astype(np.int32)
        toWarp=np.copy(toWarp, order='C')
        baseWarp=rcommon.getBaseFileName(name)
        warped=np.array(tf.warp_discrete_volumeNN(toWarp, displacement)).astype(np.int16)
        imgWarped=nib.Nifti1Image(warped, F)#The affine transformation is the reference's one
        imgWarped.to_filename('warpedDiff_'+baseWarp+'_'+baseFixed+'.nii.gz')
        #---warp using affine inly
        warped=np.array(tf.warp_discrete_volumeNNAffine(toWarp, referenceShape, initAffine)).astype(np.int16)
        imgWarped=nib.Nifti1Image(warped, F)#The affine transformation is the reference's one
        imgWarped.to_filename('warpedAffine_'+baseWarp+'_'+baseFixed+'.nii.gz')
    #---finally, the deformed lattices (forward, inverse and resdidual)---    
    lambdaParam=0.9
    maxIter=100
    tolerance=1e-4
    print 'Computing inverse...'
    inverse=np.array(tf.invert_vector_field3D(displacement, lambdaParam, maxIter, tolerance))
    residual, stats=tf.compose_vector_fields3D(displacement, inverse)
    residual=np.array(residual)
    saveDeformedLattice3D(displacement, 'latticeDispDiff_'+baseMoving+'_'+baseFixed+'.nii.gz')
    saveDeformedLattice3D(inverse, 'latticeInvDiff_'+baseMoving+'_'+baseFixed+'.nii.gz')
    saveDeformedLattice3D(residual, 'latticeResdiff_'+baseMoving+'_'+baseFixed+'.nii.gz')
    residual=np.sqrt(np.sum(residual**2,3))
    print "Mean residual norm:", residual.mean()," (",residual.std(), "). Max residual norm:", residual.max()

def testInvExponentialVSDirect(d, lambdaParam, maxIter, tolerance):
    print 'Computes the exponential of d and its inverse, then directly computes the inverse of the exponential. Compares the difference'
    expd, invexpd=tf.vector_field_exponential(d)
    invexpdDirect=tf.invert_vector_field(expd, lambdaParam, maxIter, tolerance)
    print 'Compose exp(d) with exp(d)^-1 both computed with binary exponentiation:'
    residualA=tf.compose_vector_fields(expd, invexpd)
    print 'Compose exp(d) with exp(d)^-1, the last computed directly by least squares:'
    residualB=tf.compose_vector_fields(expd, invexpdDirect)
    rcommon.plotDeformationField(residualA)
    plt.title('Residual: exp(invexp(d))');
    rcommon.plotDeformationField(residualB)
    plt.title('Residual: exp(invexpDirect(d))');
    rcommon.plotDeformationField(expd)
    plt.title('Residual: exp(d)');
    rcommon.plotDeformationField(invexpd)
    plt.title('Residual: invexp(d))');
    
def testInvertVectorField():
    lambdaParam=1
    maxIter=1000
    tolerance=1e-4
    d=rcommon.createDeformationField2D_type1(100,100,1)
    #d=rcommon.createDeformationField2D_type2(100,100,5)
    #d=rcommon.createDeformationField2D_type3(100,100,5)
    testInvExponentialVSDirect(d, lambdaParam, maxIter, tolerance)
#    invd=tf.invert_vector_field(d, lambdaParam, maxIter, tolerance)
#    expd, invexpd=tf.vector_field_exponential(d)
#    invexpdDirect=tf.invert_vector_field(expd, lambdaParam, maxIter, tolerance)
        
    
#    residual=tf.compose_vector_fields(d,invd)
#    residualexpd=tf.compose_vector_fields(expd,invexpd)
#    rcommon.plotDeformationField(d)
#    plt.title('d');
#    rcommon.plotDeformationField(invd)
#    plt.title('invd');
#    rcommon.plotDeformationField(residual)
#    plt.title('residual: d, invd');
#    rcommon.plotDeformationField(expd)
#    plt.title('expd');
#    rcommon.plotDeformationField(invexpd)
#    plt.title('invexpd');
#    rcommon.plotDeformationField(residualexpd)
#    plt.title('residual: expd, invexpd');
    
def runArcesExperiment(rootDir, lambdaParam, maxOuterIter):
    #---Load displacement field---
    dxName=rootDir+'Vx.dat'
    dyName=rootDir+'Vy.dat'
    dx=np.loadtxt(dxName)
    dy=np.loadtxt(dyName)
    GTin=np.ndarray(shape=dx.shape+(2,), dtype=np.float64)
    GTin[...,0]=dy
    GTin[...,1]=dx
    GT=GTin
    noisy=GT+np.random.normal(0.0, 0.5, GT.shape)
    #invGT=tf.invert_vector_field(GT, 0.075, 1000, 1e-7)
    invGT_fp=rcommon.invert_vector_field_fixed_point(noisy, 100, 1e-7)
    invGT_oo=tf.invert_vector_field(noisy, 2.5, 100, 1e-7)
    #GT, invExp=tf.vector_field_exponential(GTin)
    residual_fp=np.array(tf.compose_vector_fields(GT, invGT_fp))
    residual_oo=np.array(tf.compose_vector_fields(GT, invGT_oo))
    rcommon.plotDiffeomorphism(GT,invGT_fp,residual_fp,'FP')
    rcommon.plotDiffeomorphism(GT,invGT_oo,residual_oo,'OO')
    residual_fp=residual_fp[...,0]**2+residual_fp[...,1]**2
    resStats_fp=np.sqrt(residual_fp)
    print "Inverse residual fp:",resStats_fp.mean(), "(",resStats_fp.std(),")"
    residual_oo=residual_oo[...,0]**2+residual_oo[...,1]**2
    resStats_oo=np.sqrt(residual_oo)
    print "Inverse residual fp:",resStats_oo.mean(), "(",resStats_oo.std(),")"
    return
    #---Load input images---
    fnameT1=rootDir+'t1.jpg'
    fnameT2=rootDir+'t2.jpg'
    fnamePD=rootDir+'pd.jpg'
    fnameMask=rootDir+'Mascara.bmp'
    t1=plt.imread(fnameT1)[...,0].astype(np.float64)
    t2=plt.imread(fnameT2)[...,0].astype(np.float64)
    pd=plt.imread(fnamePD)[...,0].astype(np.float64)
    t1=(t1-t1.min())/(t1.max()-t1.min())
    t2=(t2-t2.min())/(t2.max()-t2.min())
    pd=(pd-pd.min())/(pd.max()-pd.min())
    mask=plt.imread(fnameMask).astype(np.float64)
    fixed=t1
    moving=t2
    maskMoving=mask>0
    maskFixed=mask>0
    fixed*=mask
    moving*=mask
    #Option 1: warp the fixed image (floating point accuracy)
    #warpedFixed=rcommon.warpImage(fixed,GT)
    #Option 2: load the warped image (integer accuracy)
    fnameWarpedFixed=rootDir+'t1-def.jpg'
    warpedFixed=plt.imread(fnameWarpedFixed).astype(np.float64)
    warpedFixed*=mask
    warpedFixed=(warpedFixed-warpedFixed.min())/(warpedFixed.max()-warpedFixed.min())
    #----------------------------------------------------
    plt.figure()
    plt.subplot(1,4,1)
    plt.imshow(t1, cmap=plt.cm.gray)
    plt.title('Input T1')
    plt.subplot(1,4,2)
    plt.imshow(t2, cmap=plt.cm.gray)
    plt.title('Input T2')
    plt.subplot(1,4,3)
    plt.imshow(pd, cmap=plt.cm.gray)
    plt.title('Input PD')
    plt.subplot(1,4,4)
    plt.imshow(mask, cmap=plt.cm.gray)
    plt.title('Input Mask')
    #-------------------------
    print 'Registering T2 (template) to deformed T1 (template)...'
    level=2
    movingPyramid=[img for img in rcommon.pyramid_gaussian_2D(moving, level, maskMoving)]
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_2D(warpedFixed, level, maskFixed)]
    plt.figure()
    plt.subplot(1,2,1)
    plt.imshow(moving, cmap=plt.cm.gray)
    plt.title('Moving')
    plt.subplot(1,2,2)
    plt.imshow(warpedFixed, cmap=plt.cm.gray)
    plt.title('Fixed')
    rcommon.plotOverlaidPyramids(movingPyramid, fixedPyramid)
    displacementList=[]
    displacement=estimateMultimodalDeformationField2DMultiScale(movingPyramid, fixedPyramid, lambdaParam, maxOuterIter, 0, displacementList)
    warpPyramid=[rcommon.warpImage(movingPyramid[i], displacementList[i]) for i in range(level+1)]
    rcommon.plotOverlaidPyramids(warpPyramid, fixedPyramid)
    rcommon.overlayImages(warpPyramid[0], fixedPyramid[0])
    rcommon.plotDeformedLattice(displacement)
    #compute statistics
    displacement[...,0]*=(maskFixed)
    displacement[...,1]*=(maskFixed)
    nrm=np.sqrt(displacement[...,0]**2 + displacement[...,1]**2)
    nrm*=maskFixed
    maxNorm=np.max(nrm)
    residual=((displacement-GT))**2
    meanDisplacementError=np.sqrt(residual.sum(2)*(maskFixed)).mean()
    stdevDisplacementError=np.sqrt(residual.sum(2)*(maskFixed)).std()
    print 'Max global displacement: ', maxNorm
    print 'Mean displacement error: ', meanDisplacementError,'(',stdevDisplacementError,')'

def runAllArcesExperiments(lambdaParam, maxOuterIter):
    rootDirs=['/opt/registration/data/arce/GT01/',
              '/opt/registration/data/arce/GT02/',
              '/opt/registration/data/arce/GT03/',
              '/opt/registration/data/arce/GT04/']
#    rootDirs=['/opt/registration/data/arce/GT02/']
    for rootDir in rootDirs:
        runArcesExperiment(rootDir, lambdaParam, maxOuterIter)
    print 'done.'

def checkInversionResults(suffix):
    import tensorFieldUtils as tf
    import registrationCommon as rcommon
    root='../inverse/experiments/'
    fnameInput=root+'displacement_clean.bin'
    fnameInverse=root+'inverse_'+suffix+'.bin'
    nrows=256
    ncols=256
    numDoubles=2*nrows*ncols
    inputField=np.array(tf.read_double_buffer(fnameInput, numDoubles)).reshape(nrows,ncols,2)
    inverseField=np.array(tf.read_double_buffer(fnameInverse, numDoubles)).reshape(nrows,ncols,2)
    residualField, stats=tf.compose_vector_fields(inputField, inverseField)
    dLattice, dInvLattice, resLattice, detJacobian=rcommon.plotDiffeomorphism(inputField,inverseField,residualField,suffix)
    plt.imsave(root+'dLattice.png', dLattice, cmap=plt.cm.gray)
    plt.imsave(root+'dInvLattice_'+suffix+'.png', dInvLattice, cmap=plt.cm.gray)
    plt.imsave(root+'resLattice_'+suffix+'.png', resLattice, cmap=plt.cm.gray)
    plt.imsave(root+'jacobian.png', detJacobian, cmap=plt.cm.gray)
    noisyField=inputField=np.array(tf.read_double_buffer(root+'displacement.bin', numDoubles)).reshape(nrows,ncols,2)
    deformedNoisy=rcommon.plotDeformedLattice(noisyField)
    plt.imsave(root+'dLatticeNoisy.png', deformedNoisy, cmap=plt.cm.gray)
    print 'Max residual:',stats[0], '. Mean:',stats[1],'(', stats[2],')'

def plotInversionGraphs():
    statsJacobi=np.loadtxt('../inverse/experiments/stats_jacobi.txt',dtype=np.float64)
    statsFixedPoint=np.loadtxt('../inverse/experiments/stats_fixedpoint.txt',dtype=np.float64)
    statsYan=np.loadtxt('../inverse/experiments/stats_yan.txt',dtype=np.float64)
    start=0
    fig=plt.figure(facecolor='white', figsize=(10, 5))
    #fig.set_figheight(350)
    #fig.set_figwidth(700)
    pJacobi,=plt.plot(statsJacobi[start:,1],'k--')
    pFixedPoint,=plt.plot(statsFixedPoint[start:,1],'k-')
    pYan,=plt.plot(statsYan[start:,1], 'k:')
    plt.yscale('log')
    plt.legend([pJacobi, pFixedPoint, pYan], ["Jacobi", "Fixed Point", "Yan's"])
    plt.title("Mean error")
    plt.xlabel("Iterations")
    plt.ylabel("Error")
    fig=plt.figure(facecolor='white', figsize=(10, 5))
    #fig.set_figheight(350)
    #fig.set_figwidth(700)
    pJacobi,=plt.plot(statsJacobi[start:,0])
    pFixedPoint,=plt.plot(statsFixedPoint[start:,0])
    pYan,=plt.plot(statsYan[start:,0])
    plt.yscale('log')
    plt.legend([pJacobi, pFixedPoint, pYan], ["Jacobi", "Fixed Point", "Yan"])
    plt.title("Maximum error")
    plt.xlabel("Iterations")
    plt.ylabel("Error")

def createInvertiblefield(m, sigma):
    displacement_clean=tf.create_invertible_displacement_field(256, 256, m, 8)
    if sigma>0:
        displacement=displacement_clean+np.random.normal(0.0, sigma, displacement_clean.shape)
    else:
        displacement=displacement_clean
    detJacobian=rcommon.computeJacobianField(displacement)
    plt.figure()
    plt.imshow(detJacobian)
    print 'Range:', detJacobian.min(), detJacobian.max()
    X1,X0=np.mgrid[0:displacement.shape[0], 0:displacement.shape[1]]
    CS=plt.contour(X0,X1,detJacobian,levels=[0.0], colors='b')
    plt.clabel(CS, inline=1, fontsize=10)
    plt.title('det(J(displacement))')
    tf.write_double_buffer(np.array(displacement).reshape(-1), '../inverse/experiments/displacement.bin')
    tf.write_double_buffer(np.array(displacement_clean).reshape(-1), '../inverse/experiments/displacement_clean.bin')
    counts=np.array(tf.count_supporting_data_per_pixel(displacement))
    plt.figure()
    plt.imshow(counts>0, cmap=plt.cm.gray)

def exportCircleToCDeformation():
    circleToCDisplacementName='circleToCDisplacement.npy'
    circleToCDisplacementInverseName='circleToCDisplacementInverse.npy'
    if(os.path.exists(circleToCDisplacementName)):
        displacement=np.load(circleToCDisplacementName)
        inverse=np.load(circleToCDisplacementInverseName)
    else:
        print 'Displacement field not found. Run diffeomorphic registration again.'
        return
    residualJoint=np.array(tf.compose_vector_fields(displacement, inverse)[0])
    rcommon.plotDiffeomorphism(displacement, inverse, residualJoint, 'D-joint')
    tf.write_double_buffer(np.array(displacement).reshape(-1), '../inverse/experiments/displacement.bin')
    tf.write_double_buffer(np.array(displacement).reshape(-1), '../inverse/experiments/displacement_clean.bin')
    counts=np.array(tf.count_supporting_data_per_pixel(displacement))
    plt.figure()
    plt.imshow(counts>0, cmap=plt.cm.gray)

def testInterpolationAdjoint():
    displacement=tf.create_invertible_displacement_field(128, 128, 0.2, 8)
    inverse_clean=tf.invert_vector_field(displacement, 0.075, 100, 1e-7)
    #############
    inverseA=inverse_clean+np.random.normal(0.0, 15.0, inverse_clean.shape)
    inverseB=inverse_clean+np.random.normal(0.0, 15.0, inverse_clean.shape)
    #############
    residualInterpolation=np.array(tf.vector_field_interpolation(displacement, inverseA))#This is A(inverseA)
    residualAdjoint=np.array(tf.vector_field_adjoint_interpolation(displacement, inverseB))#This is A*(inverseB)
    #now compare  <A(inverseA), inverseB> with <inverseA, A*(inverseB)>
    prodInterpolation=(residualInterpolation[...]*inverseB[...]).sum()
    prodAdjoint=(residualAdjoint[...]*inverseA[...]).sum()
    print (inverseB-inverseA).mean(), (inverseB-inverseA).std()
    print (residualInterpolation-residualAdjoint).mean(), (residualInterpolation-residualAdjoint).std()
    print (inverseB-residualAdjoint).mean(), (inverseB-residualAdjoint).std()
    print (inverseA-residualInterpolation).mean(), (inverseA-residualInterpolation).std()
    print prodInterpolation, prodAdjoint    

def testInverseTVL2(maxIter=10, tolerance=1e-7, m=0.2, lambdaParam=0.15):
    displacement=np.array(tf.create_invertible_displacement_field(256, 256, m, 8))
    inverse=np.array(tf.invert_vector_field_tv_l2(displacement, lambdaParam, maxIter, tolerance))
    residual=np.array(tf.compose_vector_fields(displacement, inverse)[0])
    rcommon.plotDiffeomorphism(displacement, inverse, residual, 'TV-L2')

def reviewRegistrationResults():
    import numpy as np
    import nibabel as nib
    import registrationCommon as rcommon
    prefix='data/ANTS/GOOD/'
    fixedFName=prefix+'b0_brain.nii.gz'
    movingFName=prefix+'t1_brain_on_upsamp_b0_brain.nii.gz'
    warpedFName=prefix+'t1_brain_on_upsamp_b0_brain_warped.nii.gz'
    nib_fixed=nib.load(fixedFName)
    nib_moving=nib.load(movingFName)
    nib_warped=nib.load(warpedFName)
    fixed=nib_fixed.get_data().squeeze().astype(np.float64)
    moving=nib_moving.get_data().squeeze().astype(np.float64)
    warped=nib_warped.get_data().squeeze().astype(np.float64)
    fixed=np.copy(fixed, order='C')
    moving=np.copy(moving, order='C')
    warped=np.copy(warped, order='C')
    #generate and show pyramids
    pyramidMaxLevel=3
    maskMoving=np.ones_like(moving)
    maskFixed=np.ones_like(fixed)
    maskWarped=np.ones_like(warped)
    fixedPyramid=[img for img in rcommon.pyramid_gaussian_3D(fixed, pyramidMaxLevel, maskFixed)]
    movingPyramid=[img for img in rcommon.pyramid_gaussian_3D(moving, pyramidMaxLevel, maskMoving)]
    warpedPyramid=[img for img in rcommon.pyramid_gaussian_3D(warped, pyramidMaxLevel, maskWarped)]
    rcommon.plotOverlaidPyramids3DCoronal(movingPyramid, fixedPyramid)
    rcommon.plotOverlaidPyramids3DCoronal(warpedPyramid, fixedPyramid)
    #load displacement fields
    displacementFName=prefix+'t1_brain_nonlin_transformWarp.nii.gz'
    #displacementInverseFName=prefix+'t1_brain_nonlin_transformInverseWarp.nii.gz'
    nib_displacement = nib.load(displacementFName)
    #nib_displacementInverse = nib.load(displacementInverseFName)
    displacement=nib_displacement.get_data().squeeze().astype(np.float64)
    displacement=np.copy(displacement, order='C')
    #displacementInverse=nib_displacementInverse.get_data().squeeze().astype(np.float64)
    #apply displacement and show overlaid volumes
    warped=rcommon.warpVolume(moving, displacement, nib_moving.get_affine(), nib_displacement.get_affine())
    maskWarped=np.ones_like(warped)
    warpedPyramid=[img for img in rcommon.pyramid_gaussian_3D(warped, pyramidMaxLevel, maskWarped)]
    rcommon.plotOverlaidPyramids3DCoronal(warpedPyramid, fixedPyramid)


def showOverlaidVolumes(fixedFName, movingFName):
    '''
    showOverlaidVolumes('/opt/registration/data/t1/IBSR18/IBSR_01/IBSR_01_ana_strip.nii.gz', '/opt/registration/data/affineRegistered/templateT1ToIBSR01T1.nii.gz')
    showOverlaidVolumes('/opt/registration/data/t1/IBSR18/IBSR_02/IBSR_02_ana_strip.nii.gz', '/opt/registration/data/affineRegistered/templateT1ToIBSR02T1.nii.gz')
    showOverlaidVolumes('/opt/registration/data/t1/IBSR18/IBSR_01/IBSR_01_seg_ana.nii.gz', '/opt/registration/data/t1/IBSR18/IBSR_01/IBSR_01_seg_ana.nii.gz')
    '''
    import numpy as np
    import nibabel as nib
    import registrationCommon as rcommon
    nib_fixed=nib.load(fixedFName)
    nib_moving=nib.load(movingFName)
    fixed=nib_fixed.get_data().squeeze().astype(np.float64)
    moving=nib_moving.get_data().squeeze().astype(np.float64)
    fixed=np.copy(fixed, order='C')
    moving=np.copy(moving, order='C')
    sf=np.array(fixed.shape)//2
    sm=np.array(moving.shape)//2
    rcommon.overlayImages(fixed[sf[0],:,:], moving[sm[0],:,:])
    rcommon.overlayImages(fixed[:,sf[1],:], moving[:,sm[1],:])
    rcommon.overlayImages(fixed[:,:,sf[2]], moving[:,:,sm[2]])

def buildRegistrationScript():
    ibsrPath='/opt/registration/data/t1/IBSR18/'
    templateFName='/opt/registration/data/t1/t1_icbm_normal_1mm_pn0_rf0_peeled.nii.gz'
    destinationPath='/opt/registration/data/affineRegistered/'
    with open("affineRegScript.sh","w") as f:
        for i in range(18):
            if(i<10):
                stri='0'+str(i+1)
            else:
                stri=str(i+1)
            fixedName=ibsrPath+'IBSR_'+stri+'/IBSR_'+stri+'_ana_strip.nii.gz'
            movingName=templateFName
            transformationName=destinationPath+'templateT1ToIBSR'+stri+'T1'
            warpedName=destinationPath+'templateT1ToIBSR'+stri+'T1.nii.gz'
            regCommand='ANTS 3 -m MI['+fixedName+', '+movingName+', 1, 32] -i 0 -o '+transformationName
            warpCommand='WarpImageMultiTransform 3 '+movingName+' '+warpedName+' -R '+fixedName+' '+transformationName+'Affine.txt'
            f.write(regCommand+'\n')
            f.write(warpCommand+'\n')

def testBrainwebSegmentation():
    #-------Fuzzy
    csfName='data/phantom_1.0mm_normal_csf.rawb'
    gryName='data/phantom_1.0mm_normal_gry.rawb'
    whtName='data/phantom_1.0mm_normal_wht.rawb'
    ns=181
    nr=217
    nc=181
    csf=np.fromfile(csfName, dtype=np.ubyte).reshape(ns,nr,nc)
    gry=np.fromfile(gryName, dtype=np.ubyte).reshape(ns,nr,nc)
    wht=np.fromfile(whtName, dtype=np.ubyte).reshape(ns,nr,nc)
    csf=csf.astype(np.float64)
    gry=gry.astype(np.float64)
    wht=wht.astype(np.float64)
    colorImage=np.zeros(shape=(ns, nr, nc, 3), dtype=np.int8)
    colorImage[...,0]=rcommon.renormalizeImage(csf)
    colorImage[...,1]=rcommon.renormalizeImage(gry)
    colorImage[...,2]=rcommon.renormalizeImage(wht)
    imgA=colorImage[ns/2, :, :, :]
    imgB=colorImage[:, nr/2, :, :]
    imgC=colorImage[:, :, ns/2, :]
    plt.figure()
    plt.subplot(1,3,1)
    plt.imshow(imgA)
    plt.subplot(1,3,2)
    plt.imshow(imgB)
    plt.subplot(1,3,3)
    plt.imshow(imgC)
    #-------discrete
    discreteName='data/phantom_1.0mm_normal_crisp.rawb'
    discrete=np.fromfile(discreteName, dtype=np.ubyte).reshape(ns,nr,nc)
    colorImage[...]=0
    for i in range(8):
        colorImage[discrete==i,:]=rcommon.getColor(i)
    plt.figure()
    plt.subplot(1,3,1)
    plt.imshow(imgA)
    plt.subplot(1,3,2)
    plt.imshow(imgB)
    plt.subplot(1,3,3)
    plt.imshow(imgC)
    #-------rois
    discreteName='data/t1/IBSR18/IBSR_01/IBSR_01_seg_ana.nii.gz'
    nib_discrete=nib.load(discreteName)
    discrete=nib_discrete.get_data().squeeze().astype(np.int32)
    discrete=np.copy(discrete, order='C')
    discrete=np.array(tf.consecutive_label_map(discrete))
    ns, nr, nc=discrete.shape
    colorImage=np.zeros(shape=discrete.shape+(3,), dtype=np.int8)
    for i in range(35):
        colorImage[discrete==i,:]=rcommon.getColor(i)
    imgA=colorImage[ns/2, :, :, :]
    imgB=colorImage[:, nr/2, :, :]
    imgC=colorImage[:, :, ns/2, :]
    plt.figure()
    plt.subplot(1,3,1)
    plt.imshow(imgA)
    plt.subplot(1,3,2)
    plt.imshow(imgB)
    plt.subplot(1,3,3)
    plt.imshow(imgC)

#testEstimateMultimodalDeformationField2DMultiScale(150, False):
if __name__=="__main__":
    moving=sys.argv[1]
    fixed=sys.argv[2]
    affine=sys.argv[3]
    warpDir=sys.argv[4]
    lambdaParam=np.float(sys.argv[5])
    testEstimateMultimodalNonlinearField3DMultiScale(moving, fixed, affine, warpDir, lambdaParam)
