import pandas as pd
import os
import argparse

from scipy.ndimage import median_filter
from scipy.signal import savgol_filter
from scipy.special import euler

from Photometer.constants import (
    SEPERATOR,
    PWM_DUTY_CYCLES,
    MAX_U16,
    MEASUREMENT_REPEATS,
    DATE,
    CHANNEL,
    DETECTOR,
    INTENSITY, MEASUREMENT_FREQUENCY_SECONDS,
)
import matplotlib as mpl
from matplotlib import rc
from matplotlib import pyplot as plt
from datetime import datetime
import time
import seaborn as sns

text_color = 'white'
# sns.set(
#     style="ticks",
#     context="talk",
# )
#
# sns.set(
#     # style="ticks",
#     context="talk",
# )

plt.rcParams['font.family'] = "sans-serif"
plt.rcParams['font.sans-serif'] = "Helvetica"
plt.rcParams['text.usetex'] = True
plt.rcParams['mathtext.fontset'] = 'custom'
plt.rcParams['mathtext.rm'] = "Helvetica"
rc('text.latex', preamble=r'\usepackage{cmbright}')

params = {"ytick.color" : "w",
          "xtick.color" : "w",
          "axes.labelcolor" : "w",
          "axes.edgecolor" : "w",
}
plt.rcParams.update(params)
# pd.set_option("display.precision", 60)

# plt.style.use("dark_background")
plt.rcParams['text.usetex'] = True

# /home/schwan/syncthing/PicoPhotometer/20241101-100001_output.csv

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

def make_figure(
        csv_file_path: str,
        image_file_path: str | None = None,
        df_truth: pd.DataFrame | None = None,
        yaxis_min: float | int = .0004,
        yaxis_max: float | int = 2.5,
        titles: list[str] | None = None,
) -> None:
    """ Create a figure from the measurements

    :param csv_file_path: path of .csv result file
    :param image_file_path: path to save image under
    :param df_truth: Pandas data frame with measured values
    :param yaxis_min: min value on the y-axis
    :param yaxis_max: max value on the y-axis
    :param titles: Optional list of strings for the titles of each axis
    :return: None
    """
    repeats = [i for i in range(MEASUREMENT_REPEATS)]
    column_names = [DATE, CHANNEL, DETECTOR, INTENSITY, ] + repeats

    if df_truth is not None:
        try:
            df_truth = pd.read_csv(
                args.odreader,
                sep=SEPERATOR,
                header=0,
                names=[DATE, 0, 1, 2, 3, 4, 5, 6, 7],
                date_format='%Y%m%d %H:%M',
                parse_dates=[DATE],
            )

            df_truth[DATE] = (df_truth[DATE] - df_truth[DATE].min()).dt.total_seconds() / 3600
            print(max(df_truth[DATE]))
        except pd.errors.ParserError:
            print("Couldn't read truth values, continuing without")
            df_truth = None
    try:
        df = pd.read_csv(
            filepath_or_buffer=csv_file_path,
            sep=SEPERATOR,
            header=None,
            names=column_names,
            date_format='%Y%m%d-%H%M%S',
            parse_dates=[DATE],
        )
    except pd.errors.ParserError:
        return None
    if titles is not None:
        assert len(df[CHANNEL].unique()) == len(titles), f"Wrong number of titles provided: {df[CHANNEL].unique()}"

    # Convert to hours for display
    df[DATE] = (df[DATE] - df[DATE].min()).dt.total_seconds() / 3600
    if df_truth is not None:
        print(max(df[DATE]))
        print(max(df_truth[DATE]) - max(df[DATE]))

    # Take median measurement
    df['med'] = df[repeats].median(axis=1)
    # Flip all measurements so low values are low measurements
    df['med'] = MAX_U16 - df['med']

    # Take no light measurement, expand so we can use it later
    df['fully_dark'] = df.loc[(df[INTENSITY] == PWM_DUTY_CYCLES[0]), 'med']
    df['fully_dark'] = df['fully_dark'].ffill()

    for intensity_select in PWM_DUTY_CYCLES[1:]:
        for ch in df[CHANNEL].unique():
            # @ todo: find alternative - Remove low measurement of first [5, 10] h to get ~OD 0
            #  - not great but current best fix?

            # Median filter:
            median_window = 5
            if df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch), 'med'].size > median_window:
                df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch), 'med'] = median_filter(
                    df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)]['med'],
                    size=median_window,
                    mode='nearest',
                )

                # Savitzky-Golay filter to smoothe the thing
                # df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch), 'med'] = savgol_filter(
                #     df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)]['med'],
                #     polyorder=3,
                #     window_length=median_window,
                #     mode='nearest',
                # )
            if any(df[DATE] > 10):
                df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch),
                'med'] = df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch),
                'med'] + df.loc[(df[INTENSITY] == intensity_select) & (df[CHANNEL] == ch) & (df[DATE] < 10) & (df[DATE] > 1),
                'med'].quantile(.01) * -1


    # Extrapolate from dark value, set to OD 2.5 - @todo: correct for low value subtraction
    df['med'] = (df['med'] / df['fully_dark']) * 2.5

    # fig, axes = plt.subplots(
    #     len(df[CHANNEL].unique()), 1,
    #     sharex='all',
    #     sharey='all',
    #     figsize=(10, 16 / 8 * len(df[CHANNEL].unique())),
    #     constrained_layout=True,
    # )

    for idx, (ch) in enumerate(zip(df[CHANNEL].unique())):
        fig, ax = plt.subplots(
            1, 1,
            # sharex='all',
            # sharey='all',
            figsize=(7, 3),
            # facecolor='#222222',
        )
        for int_idx, intensity_select in enumerate(PWM_DUTY_CYCLES[2:4]):
            ax.plot(
                df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)][DATE],
                df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)]['med'],
                label=f"{intensity_select/MAX_U16:.2f}",
                zorder=1+int_idx,
                c=text_color,
            )
        if df_truth is not None:
            if ch in df_truth.columns:
                # ax2 = ax.twinx()
                ax.plot(
                    df_truth[DATE],
                    df_truth[ch],
                    label="OD$_{600}$",
                    c=text_color,
                    marker='+',
                    zorder=10+idx,
                )
                # ax2.set_yscale('log')
                # ax2.set_ylim(yaxis_min, yaxis_max)
                # ax2.set_zorder(0)
        ax.set_ylim(yaxis_min, yaxis_max)
        ax.set_yscale('log')
        ax.grid(visible='both', which='both', zorder=0,)
        # if titles is not None:
        #     ax.set_ylabel(f"{titles[idx]}")
        # else:
        ax.set_ylabel("OD$_{600}$")
        # ax.legend(
        #     loc='upper left',
        #     ncols=2 if len(PWM_DUTY_CYCLES) > 3 else 1,
        #     # Transparency of the box
        #     framealpha=.5,
        #     # Length of the line in the legend
        #     handlelength=1,
        #     # title='Lamp Power',
        # )

        ax.set_xlabel('Time (h)')

        # plt.suptitle(f"{datetime.now()} ({time_since_last_mod(csv_file_path) / 60:.2f} min)")

        save_path = image_file_path if image_file_path is not None else os.path.join(
            os.path.split(csv_file_path)[0], f'img{ch}_talk.png'
        )

        plt.savefig(
            save_path,
            bbox_inches='tight',
            dpi=300,
            transparent=True,
        )
        plt.close()


def time_since_last_mod(file):
    return time.time() - os.path.getmtime(file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", "-i",
        help="input filename",
        required=True,
    )
    parser.add_argument(
        "--image_path", "-o",
        help="Image file path, optional, defaults to 'img.png' in the folder of the supplied .csv",
        default=None,
    )
    parser.add_argument(
        "--odreader", "-od",
        help="file path for tab seperated sheet of true values",
        default=None,
    )
    parser.add_argument(
        "--namelist", "-n",
        nargs='+',
        help='Names for the individual axes in the image - has to be as many as there are axes',
        default=None,
    )

    args = parser.parse_args()

    test = True
    min_time_diff = 180
    make_figure(
        csv_file_path=args.input,
        image_file_path=args.image_path,
        titles=args.namelist,
        df_truth=args.odreader,
    )
