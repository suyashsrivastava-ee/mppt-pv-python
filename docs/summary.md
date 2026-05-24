# MPPT Simulation Summary

## Comparison metrics

scenario               algorithm  avg_efficiency_pct  min_efficiency_pct  final_efficiency_pct  avg_power_w  avg_ideal_power_w  mean_abs_power_error_w  mean_duty  std_duty
constant                     P&O           99.561210           87.690223             99.730360    67.647480          67.945619                0.298139   0.577879  0.013078
constant Incremental Conductance           99.696441           87.425619             99.994879    67.739364          67.945619                0.206255   0.577997  0.011549
    step                     P&O           96.625709           63.955368             99.952559    50.443711          52.008947                1.565236   0.503110  0.069145
    step Incremental Conductance           97.540183           62.047126             99.973177    50.887445          52.008947                1.121502   0.501371  0.069631
    ramp                     P&O           95.476166           73.417895             97.731696    47.062991          48.933202                1.870211   0.490912  0.085354
    ramp Incremental Conductance           95.878546           73.852325             94.609324    47.018814          48.933202                1.914388   0.449440  0.107077