#!/usr/bin/env python3
import pathlib
import re
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
            resDF = pd.read_csv(csvFile, index_col=0).tail(1)
        else:
            resDF = pd.concat([resDF, pd.read_csv(csvFile, index_col=0).tail(1)])

    # Reconvert values form string to float64
    cols = ["RealTime", "UserTime", "KernelTime"]
    resDF[cols] = resDF[cols].apply(pd.to_numeric, errors="coerce")

    # To speed up the firesim run, xz is split into multiple concurrent runs of
    # different parts of the benchmark. We just recombine here.
    if '657.xz_s_0' in resDF.index and '657.xz_s_1' in resDF.index:
        resDF.loc['657.xz_s', :] = resDF.loc['657.xz_s_0', :] + resDF.loc['657.xz_s_1', :]
        resDF.drop(['657.xz_s_0','657.xz_s_1'], inplace=True)

    for index in resDF.index:
        resDF.loc[index, 'score'] = baseline.loc[index, 'RealTime'] / resDF.loc[index, 'RealTime']
    resDF.sort_index(inplace=True)
    return resDF


def handleRate(outDir):
    resDF = None
    for csvFile in outDir.glob("*/output/*.csv"):
        if resDF is None:
            resDF = pd.read_csv(csvFile).tail(1)
        else:
            resDF = pd.concat([resDF, pd.read_csv(csvFile).tail(1)], ignore_index=True)

    resDF.reset_index(drop=True, inplace=True)
    nameGroups = resDF.groupby(['name'])

    # Reconvert values form string to float64
    cols = ["RealTime", "UserTime", "KernelTime"]
    resDF[cols] = resDF[cols].apply(pd.to_numeric, errors="coerce")

    resDF = resDF[nameGroups['RealTime'].transform(max) == resDF['RealTime']].copy()
    resDF.drop('copy', axis=1, inplace=True)
    resDF.set_index('name', inplace=True)
    resDF = pd.concat([resDF, nameGroups['copy'].count().rename("ncopy")], axis=1)

    resDF['score'] = (specRateReference['RealTime'] / resDF['RealTime']) * resDF['ncopy']

    return resDF


# ---------------------------------------------------------------------------
# TMA: parse the printf blocks emitted by tma_inject.c's dtor. Every speed
# binary has tma_inject.o (linked via riscv.cfg EXTRA_LIBS); its ctor
# captures snapshot1 before main() and its dtor captures snapshot2 + prints
# both as CSV blocks at exit. Per-job stdout lands at <job>/uartlog.
#
# Format (two blocks per uartlog, snapshot1 then snapshot2):
#   ===== TMA PERFORMANCE COUNTERS =====
#   counter,value
#   cycles,12345
#   instret,6789
#   ...
#   ====================================
#
# Legacy SynthesizePrintf format (a single `name = value` block) is also
# accepted as a fallback for old binaries / pre-software-printf runs.
# ---------------------------------------------------------------------------

_TMA_HEADER     = re.compile(r"^={5} TMA PERFORMANCE COUNTERS ={5}\s*$")
_TMA_FOOTER     = re.compile(r"^={36}\s*$")
_TMA_CSV_HEADER = re.compile(r"^counter,value\s*$")
_TMA_LINE_CSV   = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*),(\d+)\s*$")
_TMA_LINE_KV    = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)\s*$")


def _parseTMAblocks(text):
    """Parse all TMA blocks in `text`, in document order. Each block is
    delimited by a `===== TMA PERFORMANCE COUNTERS =====` header and a
    36-equals footer. Payload rows match either the new CSV format
    (`name,value`) or the legacy synth-printf format (`name = value`); the
    `counter,value` CSV column header is skipped.

    Returns list of dict[counter_name, int]."""
    blocks = []
    cur = None
    for line in text.splitlines():
        if _TMA_HEADER.match(line):
            cur = {}
            continue
        if cur is not None and _TMA_FOOTER.match(line):
            blocks.append(cur)
            cur = None
            continue
        if cur is not None:
            if _TMA_CSV_HEADER.match(line):
                continue
            m = _TMA_LINE_CSV.match(line) or _TMA_LINE_KV.match(line)
            if m:
                cur[m.group(1)] = int(m.group(2))
    return blocks


def _parseTMAblock(text):
    """Return dict[counter_name, int] of (snapshot2 - snapshot1) deltas for
    the two CSV blocks tma_inject.c's dtor emits. If only one block is
    found (legacy synth-printf path), return that block's values directly.
    Return None if no block."""
    blocks = _parseTMAblocks(text)
    if not blocks:
        return None
    if len(blocks) == 1:
        return blocks[0]
    s1, s2 = blocks[0], blocks[-1]
    return {k: s2[k] - s1[k] for k in (set(s1) & set(s2))}


def _findConsoleLog(jobDir):
    """firemarshal writes <job>/uartlog (launch.py:136); fall back to any
    *.log under the job dir for FireSim-cloud-style harnesses."""
    uartlog = jobDir / "uartlog"
    if uartlog.exists():
        return uartlog
    for cand in jobDir.glob("*.log"):
        return cand
    return None


def handleTMA(outDir):
    rows = []
    for jobDir in sorted(p for p in outDir.iterdir() if p.is_dir()):
        log = _findConsoleLog(jobDir)
        if log is None:
            continue
        try:
            text = log.read_text(errors="replace")
        except Exception as e:
            print(f"Warning: cannot read {log}: {e}")
            continue
        counters = _parseTMAblock(text)
        if counters is None:
            continue
        rows.append(pd.Series(counters, name=jobDir.name))
    if not rows:
        return None
    tmaDF = pd.DataFrame(rows)
    tmaDF.index.name = 'name'
    tmaDF.sort_index(inplace=True)
    if 'instret' in tmaDF.columns and 'cycles' in tmaDF.columns:
        ipc = tmaDF['instret'] / tmaDF['cycles']
        insert_after = max(tmaDF.columns.get_loc('instret'),
                           tmaDF.columns.get_loc('cycles'))
        tmaDF.insert(insert_after + 1, 'IPC', ipc)
    return tmaDF


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

    # Process TMA counters if available (intspeed only — intrate isn't
    # instrumented; see riscv.cfg `intspeed,fpspeed:` block)
    tmaDF = handleTMA(args.outputPath)
    if tmaDF is not None:
        with open(args.outputPath / "tma_results.csv", "w") as f:
            f.write(tmaDF.to_csv())
        print("TMA results available in: ", args.outputPath / "tma_results.csv")

    print("Output available in: ", args.outputPath)
