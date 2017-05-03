# -*- coding: utf-8 -*-

from skimage import io
import numpy as np
import random
import matplotlib.pyplot as plt

# global params
fld = 'data/'

sateliteImages = ['20090526', '20110514', '20120524', '20130608',
                  '20140517', '20150507', '20160526']
alt = 'DEM_altitude.tif'
slp = 'DEM_slope.tif'


def loadSateliteFile(date, normalize=True):
    img = io.imread(fld + date + ".tif").astype(np.float32)
    ndvi = io.imread(fld + date + "_NDVI.tif").astype(np.float32)
    mask = io.imread(fld + date + "_mask_ls.tif").astype(np.float32)
    if normalize:
        img /= 20000.0
        ndvi /= 255.0  # TODO too high ?
    return img, ndvi, mask


def loadStaticData(normalize=True):
    altitude = io.imread(fld + alt).astype(np.float32)
    slope = io.imread(fld + slp).astype(np.float32)
    if normalize:
        altitude /= 2555.0
        slope /= 52.0
    return altitude, slope


def extractPatch(data, pos, size):
    x, y = pos
    diff = size // 2
    patch = data[x - diff:x + diff + 1, y - diff:y + diff + 1, :]
    return patch


def loadLandslideDataset(dates):
    last_image = None  # TODO maybe replace by another flag
    satelite_images = []
    dates = [dates[0]] + dates
    for date in dates:
        img, nvdi, mask = loadSateliteFile(date)
        image = np.concatenate((img, np.expand_dims(nvdi, 2)), axis=2)
        if last_image != None:
            image = np.concatenate((image, last_image), axis=2)
            satelite_images.append((image, mask))
        else:
            last_image = image

    altitude, slope = loadStaticData()

    return satelite_images, altitude, slope


def getLandslideDataFor(date):
    date_idx = sateliteImages.index(date)
    prev_date_idx = date_idx - 1 if date_idx >= 1 else 0
    img, nvdi, mask = loadSateliteFile(date)
    prev_img, prev_nvdi, prev_mask = loadSateliteFile(sateliteImages[prev_date_idx])
    image = np.concatenate((img, np.expand_dims(nvdi, 2)), axis=2)
    prev_image = np.concatenate((prev_img, np.expand_dims(prev_nvdi, 2)), axis=2)
    image = np.concatenate((image, prev_image), axis=2)
    return image, mask


def LandslideGenerator(date, size=25, normalize=True):
    # TODO what happens with size==0? Does even numbers make sense?
    # load data
    sat_image, mask = getLandslideDataFor(date)
    altitude, slope = loadStaticData()
    # generate coordinates (one for each set of lables)
    positive = zip(*np.where(mask == 1))
    negative = zip(*np.where(mask == 0))
    # TODO sample ratio of p from s1 and (1-p) from s2
    # extract patches (subimages) of positive and negative samples
    correctSize = lambda x: x.shape == (size, size, 12)
    sample_pos = list(filter(correctSize, map(lambda x: extractPatch(sat_image, x, size), positive)))
    sample_neg = list(filter(correctSize, map(lambda x: extractPatch(sat_image, x, size), negative)))
    # combine to np batch and return
    X = np.stack(sample_pos + sample_neg)
    y = np.concatenate((
        np.ones((len(sample_pos)), dtype=np.float32),
        np.zeros((len(sample_neg)), dtype=np.float32)
    ))
    return X, y


def getTrainDataForDir(year=2, areaSize=8, seed=1, numNeg=100):
    altMatrix = np.array(io.imread(fld + alt), dtype=np.float32) / 2555.0
    slpMatrix = np.array(io.imread(fld + slp), dtype=np.float32) / 52.0

    orgi = np.array(io.imread(fld + fimgs[year]), dtype=np.float32) / 20000.0
    addi = np.array(io.imread(fld + nimgs[year]), dtype=np.float32) / 20000.0

    porgi = np.array(io.imread(fld + fimgs[year - 1]), dtype=np.float32) / 20000.0
    paddi = np.array(io.imread(fld + nimgs[year - 1]), dtype=np.float32) / 20000.0

    resi = io.imread(fld + masks[year])

    (posXIDs, posYIDs) = np.where(resi == 1.0)
    (negXIDs, negYIDs) = np.where(resi == 0.0)

    # create train data for one episode
    # create positive instances

    diffSize = areaSize // 2

    numPos = len(posXIDs)
    posIDs = np.arange(numPos)
    negIDs = np.arange(len(negXIDs))
    random.seed(seed)
    random.shuffle(negIDs)
    useNegIDs = np.min([len(negIDs), numNeg * numPos])
    negIDs = negIDs[0:useNegIDs]
    numInstances = len(posIDs) + len(negIDs)
    label = np.zeros([numInstances, 1])
    dataPre = np.zeros([numInstances, areaSize, areaSize, orgi.shape[2]])
    dataPost = np.zeros([numInstances, areaSize, areaSize, orgi.shape[2]])
    dataSLP = np.zeros([numInstances, 1])
    dataALT = np.zeros([numInstances, 1])
    dataNDVI = np.zeros([numInstances, 1])
    counter = 0
    for posID in posIDs:
        label[counter] = 1.0
        curX = posXIDs[posID]
        curY = posYIDs[posID]
        orgiTmp = orgi[curX - diffSize:curX + diffSize, curY - diffSize:curY + diffSize, :]
        dataPost[counter, 0:orgiTmp.shape[0], 0:orgiTmp.shape[1], 0:orgiTmp.shape[2]] = orgiTmp
        preTmp = porgi[curX - diffSize:curX + diffSize, curY - diffSize:curY + diffSize, :]
        dataPre[counter, 0:orgiTmp.shape[0], 0:orgiTmp.shape[1], 0:orgiTmp.shape[2]] = preTmp
        dataALT[counter] = altMatrix[curX, curY]
        dataSLP[counter] = slpMatrix[curX, curY]
        dataNDVI[counter] = addi[curX, curY] - paddi[curX, curY]
        counter += 1

    for negID in negIDs:
        label[counter] = 0.0
        curX = negXIDs[negID]
        curY = negYIDs[negID]
        orgiTmp = orgi[curX - diffSize:curX + diffSize, curY - diffSize:curY + diffSize, :]
        dataPost[counter, 0:orgiTmp.shape[0], 0:orgiTmp.shape[1], 0:orgiTmp.shape[2]] = orgiTmp
        preTmp = porgi[curX - diffSize:curX + diffSize, curY - diffSize:curY + diffSize, :]
        dataPre[counter, 0:orgiTmp.shape[0], 0:orgiTmp.shape[1], 0:orgiTmp.shape[2]] = preTmp
        dataALT[counter] = altMatrix[curX, curY]
        dataSLP[counter] = slpMatrix[curX, curY]
        dataNDVI[counter] = addi[curX, curY] - paddi[curX, curY]
        counter += 1
    return (dataPre, dataPost, dataALT, dataSLP, dataNDVI, label)


if __name__ == "__main__":
    # parameter
    areaSize = 4
    seed = 1
    numNeg = 10
    trainYears = [1, 2, 3, 4, 5]
    testYear = 6
    # create validation set
    # (dataPreTest, dataPostTest, dataALTTest, dataSLPTest, dataNDVITest, labelTest) = getTrainDataForDir(year=testYear,
    #                                                                                                    areaSize=areaSize,
    #                                                                                                    seed=seed,
    #                                                                                                    numNeg=numNeg)
    print("All Done!")