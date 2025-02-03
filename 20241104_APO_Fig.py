import argparse
import pandas as pd
import numpy as np
import seaborn as sns
import os
import io

from scipy.ndimage import median_filter


from Photometer.constants import SEPERATOR, PWM_DUTY_CYCLES, MAX_U16
from scipy import stats
from matplotlib import pyplot as plt
import matplotlib as mpl
from datetime import datetime
import time
from matplotlib import rc

test_file = '/home/schwan/syncthing/PicoPhotometer/20200101-100001_output.csv'

text_color = 'black'
# sns.set(
#     # style="ticks",
#     # context="talk",
# )

plt.rcParams['font.family'] = "sans-serif"
plt.rcParams['font.sans-serif'] = "Helvetica"
plt.rcParams['text.usetex'] = True
plt.rcParams['mathtext.fontset'] = 'custom'
plt.rcParams['mathtext.rm'] = "Helvetica"
rc('text.latex', preamble=r'\usepackage{cmbright}')

params = {
    "ytick.color": text_color,
    "xtick.color": text_color,
    "axes.labelcolor": text_color,
    "axes.edgecolor": text_color,
    # "figure.facecolor": "#222222"
}

plt.rcParams.update(params)
# pd.set_option("display.precision", 60)

# plt.style.use("dark_background")
plt.rcParams['text.usetex'] = True
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
# facecolor = '.8'

DATE = 'Date'
CHANNEL = 'Channel'
DETECTOR = 'Detector'
INTENSITY = 'Intensity'
REP0 = 0
REP1 = 1
REP2 = 2
REP3 = 3
REP4 = 4

truth = """
DATE	1	2	3	4	5	6
20241030 16:18	0.01	0.01	0.02	0.02	0.03	0.02
20241030 18:06	0.01	0.01	0.02	0.01	0.02	0.00
20241031 10:03	0.02	0.00	0.03	0.01	0.01	0.00
20241031 14:19	0.01	0.01	0.03	0.02	0.02	0.01
20241031 17:04	0.01	0.01	0.04	0.02	0.02	0.02
20241101 10:27	0.03	0.04	0.08	0.01	0.02	0.01
20241101 12:43	0.04	0.05	0.10	0.02	0.02	0.02
20241101 14:15	0.04	0.06	0.10	0.01	0.02	0.02
20241101 16:30	0.04	0.07	0.11	0.01	0.01	0.01
20241101 17:34	0.05	0.08	0.13	0.02	0.02	0.01
20241102 11:34	0.23	0.33	0.52	0.01	0.02	0.01
20241103 09:57	0.70	0.95	1.20	0.01	0.02	0.02
20241104 09:35	1.20	1.30	1.40	0.02	0.01	0.02
"""

df_truth = pd.read_csv(
    io.StringIO(truth),
    sep='\t',
    header=0,
    names=[DATE, 1, 2, 3, 4, 5, 6],
    date_format='%Y%m%d %H:%M',
    parse_dates=[DATE],
)

df_truth[DATE] = (df_truth[DATE] - df_truth[DATE].min()).dt.total_seconds() / 3600

intensity_select = PWM_DUTY_CYCLES[4]

if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description="Process a file.")
    # parser.add_argument('file_path', type=str, help='Path to the input file')
    #
    # args = parser.parse_args()
    # file = args.file_path
    first = True
    test = 1
    while test:
        if test > 0:
            test -= 1
        file = test_file
        df = pd.read_csv(
            file,
            sep=SEPERATOR,
            header=None,
            names=[DATE, CHANNEL, DETECTOR, INTENSITY, REP0, REP1, REP2, REP3, REP4],
            # 20200101-100024	0	8	0	1280	1232	1264	1232	1216
            date_format='%Y%m%d-%H%M%S',
            parse_dates=[DATE],
        )

        df[DATE] = (df[DATE] - df[DATE].min()).dt.total_seconds() / 3600
        for r in [REP0, REP1, REP2, REP3, REP4]:
            df[r] = MAX_U16 - df[r]

        y_max = -1
        y_min = MAX_U16
        # Create average values for measurements
        # @todo: outlier removal through more measurements
        df['avg'] = df[[REP0, REP1, REP2, REP3, REP4]].median(axis=1)

        # Make a column with the values for no-light measurements, propagate values so we can subtract them later
        df['baseline'] = MAX_U16 - df.loc[(df[INTENSITY] == PWM_DUTY_CYCLES[0]), 'avg']
        df['baseline'] = df['baseline'].ffill()

        for intensity_select in PWM_DUTY_CYCLES[1:]:
            for ch in df[CHANNEL].unique():
                # Remove baseline dark value @todo: addition instead of subtract?
                df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch),
                'avg'] = df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch),
                'avg'] - df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch),
                'baseline']
                df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch),
                    'avg'] = df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch),
                    'avg'] + df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch) & (df[DATE] < 10),
                    'avg'].quantile(.1) * -1
                df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch),
                'avg'] = median_filter(
                    df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)]['avg'],
                    size=7,
                    mode='nearest',
                )

        in_max = df.loc[(df[INTENSITY] == PWM_DUTY_CYCLES[2]), 'avg'].max()
        in_min = df.loc[(df[INTENSITY] == PWM_DUTY_CYCLES[2]) & (df[DATE] < 10), 'avg'].quantile(.9)
        # df['avg'] = 0.01 + (df['avg'] - in_min) * ((1.4 - 0.01) / (in_max - in_min))
        df['avg'] = df['avg'] / df.loc[(df[INTENSITY] == PWM_DUTY_CYCLES[2]),
                'avg'].max()
        df['avg'] = df['avg'] * 1.4


        print(df.tail(40))

        fig, axes = plt.subplots(
            # len(df[CHANNEL].unique()), 1,
            2, 1,
            sharex='all',
            sharey='all',
            figsize=(10, 7),
            constrained_layout=True,
        )

        if test:
            print(df.tail(40))
        ax1 = axes[0]
        ax2 = axes[1]

        for intensity_select in PWM_DUTY_CYCLES[2:3]:
            # for ch in df[CHANNEL].unique():
            #     df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch), 'avg'] = df.loc[
            #         (df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch), 'avg'] - df.loc[
            #         (df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch), 'avg'].quantile(.01)

            y_max = max(df.loc[df[INTENSITY] == intensity_select, 'avg'].max() + df.loc[
                df[INTENSITY] == intensity_select, 'avg'].max() * .1, y_max)
            y_min = min(df.loc[df[INTENSITY] == intensity_select, 'avg'].quantile(.01) - df.loc[
                df[INTENSITY] == intensity_select, 'avg'].quantile(.99) * .1, y_min)

            # for ch, ax in zip(df[CHANNEL].unique(), axes):

            names = [
                '$S$. $oneidensis$ $\Delta$$fccA$ with $G$. $sulfurreducens$ $\Delta$1620-4, triplicate',
                '$S$. $oneidensis$ $\Delta$$fccA$ with $G$. $sulfurreducens$ $\Delta$1620-4 $\Delta$0777-85, triplicate'
            ]
            for ch in df[CHANNEL].unique()[1:4]:
                ax1.plot(
                    df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)][DATE],
                    df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)]['avg'],
                )
                # for r in [REP0, REP1, REP2, REP3, REP4]:
                #     ax.plot(
                #         df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)][DATE],
                #         df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)][r],
                #     )
            ax1.set_title(names[0])
            for ch in df[CHANNEL].unique()[4:7]:
                ax2.plot(
                    df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)][DATE],
                    df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)]['avg'],
                )
                # for r in [REP0, REP1, REP2, REP3, REP4]:
                #     ax.plot(
                #         df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)][DATE],
                #         df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)][r],
                #     )

            ax2.set_title(names[1])
            for ax in axes:
                # ax.set_ylim(100, None)
                ax.set_yscale('log')
                ax.grid(visible='both', which='both')
                # ax.ticklabel_format(axis='y', style='sci', scilimits=(0,0))
                ax.set_ylabel('OD$_{600}$')
                pass
            ax2.set_xlabel('Time (h)')
        # plt.suptitle(f"{datetime.now()}")
        # plt.savefig(
        #     '/home/schwan/fig.png',
        #     bbox_inches='tight',
        #     dpi=300,
        # )
        plt.show()
        plt.close()
        print(f"Ding: {datetime.now()}")
        if first:
            time.sleep(5)
            first = False
        else:
            time.sleep(900)
