#!/usr/bin/env python3
import pathlib
import sys
import pandas as pd
import argparse

# All time measurements are in seconds

# rate suite not supported yet
# Reference times taken from https://www.spec.org/cpu2017/results/res2017q2/cpu2017-20161026-00003.html
specRateReference = pd.DataFrame.from_dict({
    "500.perlbench_r" : 1591,
    "502.gcc_r" : 1415,
    "505.mcf_r" : 1615,
    "520.omnetpp_r" : 1311,
    "523.xalancbmk_r" : 1055,
    "525.x264_r" : 1751,
    "531.deepsjeng_r" : 1145,
    "541.leela_r" : 1655,
    "548.exchange2_r" : 2619,
    "557.xz_r" : 1076
    }, orient='index', columns=['RealTime'])

# Reference times taken from https://www.spec.org/cpu2017/results/res2017q2/cpu2017-20161026-00004.html
specSpeedReference = pd.DataFrame.from_dict({
    "600.perlbench_s" : 1774,
    "602.gcc_s" : 3976,
    "605.mcf_s" : 4721,
    "620.omnetpp_s" : 1630,
    "623.xalancbmk_s" : 1417,
    "625.x264_s" : 1763,
    "631.deepsjeng_s" : 1432,
    "641.leela_s" : 1703,
    "648.exchange2_s" : 2939,
    "657.xz_s" : 6182
    }, orient='index', columns=['RealTime'])

# This is taken from agfi-0fa2162c2c1a475d4
# (firesim-rocket-quadcore-no-nic-l2-llc4mb-ddr3 circa oct 13 2020)
# specSpeedTest = pd.DataFrame.from_dict({
#     "600.perlbench_s" : 59.87,
#     "602.gcc_s" : 0.04,
#     "605.mcf_s" : 32.12,
#     "620.omnetpp_s" : 10.15,
#     "623.xalancbmk_s" : 0.31,
#     "625.x264_s" : 188.23,
#     "631.deepsjeng_s" : 31.40,
#     "641.leela_s" : 12.17,
#     "648.exchange2_s" : 31.59,
#     "657.xz_s" : 3.71 # note that the marshal workload splits xz into two jobs to save some runtime, these are recombined during load
#     }, orient='index', columns=['RealTime'])

# Pieced together from the spec repo: spec2017/benchspec/CPU/*/data/test/reftime
specSpeedTest = pd.DataFrame.from_dict({
    "600.perlbench_s" : 74,
    "602.gcc_s" : 2,
    "605.mcf_s" : 40,
    "620.omnetpp_s" : 16,
    "623.xalancbmk_s" : 2,
    "625.x264_s" : 186,
    "631.deepsjeng_s" : 41,
    "641.leela_s" : 17,
    "648.exchange2_s" : 74,
    "657.xz_s" : 30
    }, orient='index', columns=['RealTime'])

def handleSpeed(outDir, dataset):
    if dataset == 'test':
        baseline = specSpeedTest
    elif dataset == 'ref':
        baseline = specSpeedReference
    else:
        baselinePath = pathlib.Path(dataset)
        if not baselinePath.exists():
            raise RuntimeError("Baseline csv doesn't exist: ", dataset)
        baseline = pd.read_csv(baselinePath, index_col=0)
 
    resDF = None
    for csvFile in outDir.glob("*/output/*.csv"):
        if resDF is None:
            resDF = pd.read_csv(csvFile, index_col=0)
        else:
            resDF = resDF.append(pd.read_csv(csvFile, index_col=0))

    # To speed up the firesim run, xz is split into multiple concurrent runs of
    # different parts of the benchmark. We just recombine here.
    resDF.loc['657.xz_s', :] = resDF.loc['657.xz_s_0', :] + resDF.loc['657.xz_s_1', :]
    resDF.drop(['657.xz_s_0','657.xz_s_1'], inplace=True)

    resDF['score'] = baseline['RealTime'] / resDF['RealTime']
    resDF.sort_index(inplace=True)
    return resDF


def handleRate(outDir):
    resDF = None
    for csvFile in outDir.glob("*/output/*.csv"):
        if resDF is None:
            resDF = pd.read_csv(csvFile)
        else:
            resDF = resDF.append(pd.read_csv(csvFile))

    nameGroups = resDF.groupby(['name'])

    resDF = resDF[nameGroups['RealTime'].transform(max) == resDF['RealTime']].copy()
    resDF.drop('copy', axis=1, inplace=True)
    resDF.set_index('name', inplace=True)
    resDF = pd.concat([resDF, nameGroups['copy'].count().rename("ncopy")], axis=1)

    resDF['score'] = (specRateReference['RealTime'] / resDF['RealTime']) * resDF['ncopy']

    return resDF


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aggregate results from a run of a SPEC suite")
    parser.add_argument('-s', '--suite', required=True, choices=['intspeed', 'intrate'], help="Which suite was run.")
    parser.add_argument('-d', '--dataset', required=True, help="Which dataset was used, either test or ref. You can also specify a path to a previous output of this script to use as a baseline.")
    parser.add_argument('outputPath', type=pathlib.Path, help="Output directory to process")

    args = parser.parse_args()

    if args.suite == "intspeed":
        resDF = handleSpeed(args.outputPath, dataset=args.dataset)
    elif args.suite == "intrate":
        resDF = handleRate(args.outputPath)

    with open(args.outputPath / "results.csv", "w") as f:
        f.write(resDF.to_csv())

    plot = resDF['score'].plot(kind="bar", title="SPEC Score")
    plot.get_figure().savefig(args.outputPath / "results.pdf", bbox_inches = "tight")
    print("Output available in: ", args.outputPath)
