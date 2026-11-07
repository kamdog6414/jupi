All CSVs in this directory are synthetic qualification data, not sensor measurements.
calibration-synthetic.csv uses y=2.5*x-0.75+0.02*sin(0.17*i).
new-samples-synthetic.csv can be applied to the resulting calibration.
large-offset-synthetic.csv demonstrates centering/scaling before float32 GPU work.
Always pass --synthetic for these files.
