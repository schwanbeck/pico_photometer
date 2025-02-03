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
from matplotlib import pyplot as plt
from datetime import datetime
import time

'''
# Example true value data frame:
truth = """
DATE	1	2	3	4	5	6
20241030 16:18	0.01	0.01	0.02	0.02	0.03	0.02
20241030 18:06	0.01	0.01	0.02	0.01	0.02	0.005
20241031 10:03	0.02	0.005	0.03	0.01	0.01	0.005
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
20241104 16:18	1.30	1.35	1.40	0.02	0.02	0.02
"""

df_truth = pd.read_csv(
    io.StringIO(truth),
    sep=SEPERATOR,
    header=0,
    names=[DATE, 1, 2, 3, 4, 5, 6],
    date_format='%Y%m%d %H:%M',
    parse_dates=[DATE],
)

df_truth[DATE] = (df_truth[DATE] - df_truth[DATE].min()).dt.total_seconds() / 3600
'''

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

    fig, axes = plt.subplots(
        len(df[CHANNEL].unique()), 1,
        sharex='all',
        sharey='all',
        figsize=(10, 16 / 8 * len(df[CHANNEL].unique())),
        constrained_layout=True,
    )

    for idx, (ch, ax) in enumerate(zip(df[CHANNEL].unique(), axes)):
        for int_idx, intensity_select in enumerate(PWM_DUTY_CYCLES[1:]):
            ax.plot(
                df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)][DATE],
                df.loc[(df[CHANNEL] == ch) & (df[INTENSITY] == intensity_select)]['med'],
                label=f"{intensity_select/MAX_U16:.2f}",
                zorder=1+int_idx,
            )
        if df_truth is not None:
            if ch in df_truth.columns:
                # ax2 = ax.twinx()
                ax.plot(
                    df_truth[DATE],
                    df_truth[ch],
                    label="OD$_{600}$",
                    c='black',
                    marker='+',
                    zorder=10+idx,
                )
                # ax2.set_yscale('log')
                # ax2.set_ylim(yaxis_min, yaxis_max)
                # ax2.set_zorder(0)
        ax.set_ylim(yaxis_min, yaxis_max)
        ax.set_yscale('log')
        ax.grid(visible='both', which='both', zorder=0,)
        if titles is not None:
            ax.set_ylabel(f"{titles[idx]}")
        else:
            ax.set_ylabel(f"Ch {ch}")
        ax.legend(
            loc='upper left',
            ncols=2 if len(PWM_DUTY_CYCLES) > 3 else 1,
            # Transparency of the box
            framealpha=.5,
            # Length of the line in the legend
            handlelength=1,
            # title='Lamp Power',
        )

    axes[-1].set_xlabel('Time (h)')

    plt.suptitle(f"{datetime.now()} ({time_since_last_mod(csv_file_path) / 60:.2f} min)")

    save_path = image_file_path if image_file_path is not None else os.path.join(
        os.path.split(csv_file_path)[0], 'img.png'
    )

    plt.savefig(
        save_path,
        bbox_inches='tight',
        dpi=300,
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
    while True:
        try:
            print(f"Ding: {datetime.now()}")
            make_figure(
                csv_file_path=args.input,
                image_file_path=args.image_path,
                titles=args.namelist,
                df_truth=args.odreader,
            )
            time_mod = time_since_last_mod(args.input)
            if test:
                print(time_mod)
            if MEASUREMENT_FREQUENCY_SECONDS > time_mod > min_time_diff:
                time.sleep(MEASUREMENT_FREQUENCY_SECONDS - time_mod)
            time_mod = time_since_last_mod(args.input)
            if test:
                print(time_mod)
            if time_mod > 3 * MEASUREMENT_FREQUENCY_SECONDS:
                time.sleep(MEASUREMENT_FREQUENCY_SECONDS)
            else:
                time_check_error = MEASUREMENT_FREQUENCY_SECONDS
                while time_mod < min_time_diff and time_check_error:
                    time_mod = time_since_last_mod(args.input)
                    if time_mod < (min_time_diff - 2) // 2:
                        time.sleep((min_time_diff - 2) // 2)
                    time_check_error -= 1
                    time.sleep(1)
            test = False
        except KeyboardInterrupt:
            print('Stopping')
            break