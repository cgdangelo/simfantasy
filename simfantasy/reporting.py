from abc import abstractmethod, ABC
from math import pi

import bokeh.io
import bokeh.layouts
import bokeh.models
import bokeh.palettes
import bokeh.plotting
import bokeh.transform
import numpy as np
import pandas as pd


class Reporter(ABC):
    def __init__(self, sim, df: pd.DataFrame) -> None:
        super().__init__()

        self.sim = sim
        self.df = df

    @abstractmethod
    def report(self):
        pass


class TerminalReporter(Reporter):
    def report(self):
        pd.set_option('display.width', None)

        mean_dps = (self.df.groupby([self.df.index, 'actor'])['damage'].sum()) / self.sim.combat_length.total_seconds()
        mean_dps = mean_dps.groupby('actor').mean().to_frame()
        self.sim.logger.info('Average DPS:\n\n%s\n', mean_dps)

        def pct_total(x):
            return np.sum(x) / self.df.groupby('actor')['damage'].sum() * 100

        grouped = self.df.groupby(['actor', 'action'])
        mean_dmg_per_action_df = grouped['damage'] \
            .agg([np.size, np.sum, pct_total, np.mean]) \
            .rename(columns={'size': '#'}) \
            .join(grouped['critical', 'direct'].mean() * 100) \
            .sort_values(by='sum', ascending=False)
        self.sim.logger.info('Damage dealt:\n\n%s\n', mean_dmg_per_action_df)


class HTMLReporter(Reporter):
    def report(self):
        bokeh.io.output_file('report.html')

        mean_dmg_per_action_df = self.df.groupby('action')['damage'].mean().sort_values().to_frame()
        mean_dmg_per_action = bokeh.plotting.figure(y_range=list(mean_dmg_per_action_df.index),
                                                    title='Mean Damage per Action')
        mean_dmg_per_action.hbar(y='action', right='damage', height=0.5,
                                 source=bokeh.models.ColumnDataSource(mean_dmg_per_action_df),
                                 fill_color=bokeh.transform.factor_cmap('action',
                                                                        palette=bokeh.palettes.inferno(
                                                                            len(mean_dmg_per_action_df.index)),
                                                                        factors=sorted(mean_dmg_per_action_df.index)))
        dps_per_iteration_df = (
                self.df.groupby(self.df.index)['damage'].sum() / self.sim.combat_length.total_seconds()).to_frame()
        dps_per_iteration = bokeh.plotting.figure(title='DPS per Iteration')
        dps_per_iteration.circle(x='iteration', y='damage', source=bokeh.models.ColumnDataSource(dps_per_iteration_df),
                                 size=10, alpha=0.5)

        total_dmg = self.df['damage'].sum()
        action_damage_df = (self.df.groupby('action')['damage'].sum() / total_dmg).to_frame()
        action_damage_pie = bokeh.plotting.figure(title='Damage Distribution', tools=[pie_hovertool])

        pie_slices = [p * 2 * pi for p in action_damage_df['damage'].sort_values().cumsum()]

        action_damage_pie.wedge(x=0, y=0, radius=1,
                                start_angle=pie_slices[:-1],
                                end_angle=pie_slices[1:],
                                fill_color=bokeh.palettes.inferno(len(action_damage_df) - 1))

        layout = bokeh.layouts.layout([mean_dmg_per_action, dps_per_iteration], action_damage_pie)

        bokeh.io.save(layout)
