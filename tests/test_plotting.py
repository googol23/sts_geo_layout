import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sts_geo_layout import LadderLayout, SensorType
from sts_geo_layout.plotting import plot_layout


def test_plot_uses_the_model_bounds_and_returns_a_figure(tmp_path):
    nominal = LadderLayout([SensorType(1)] * 4)
    figure = plot_layout(nominal)
    try:
        assert len(figure.axes[0].patches) == nominal.n_sensors
        assert figure.axes[0].patches[0].get_width() == 62
        output = tmp_path / "layout.png"
        figure.savefig(output)
        assert output.is_file()
    finally:
        plt.close(figure)
