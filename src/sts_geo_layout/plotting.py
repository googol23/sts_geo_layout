"""Optional Matplotlib presentation; importing the model never imports plotting."""

from .model import LadderLayout

COLOR_BY_SIZE = {22: "red", 42: "green", 62: "cyan", 124: "blue"}


def plot_layout(layout: LadderLayout, ax=None):
    """Draw the sensor footprint and return its Matplotlib figure."""
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except ImportError as error:
        raise RuntimeError(
            "Plotting requires: pip install 'sts-geo-layout[plot]'"
        ) from error

    if ax is None:
        _, ax = plt.subplots(figsize=(5, 10))
    for sensor, (xmin, xmax, ymin, ymax) in zip(
        layout.sensor_types, layout.sensor_bbox()
    ):
        ax.add_patch(
            Rectangle(
                (xmin, ymin),
                xmax - xmin,
                ymax - ymin,
                facecolor=COLOR_BY_SIZE[sensor.size_xy()[1]],
                edgecolor="black",
                alpha=0.3,
            )
        )
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.margins(0.1)
    ax.set_xlabel("X [mm]")
    ax.set_ylabel("Y [mm]")
    ax.grid(True, linestyle="--", linewidth=0.5)
    return ax.figure
