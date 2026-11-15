# SAR-Pulse: 2-minute demo script

The demo is live at the deployed site. Everything below is real data and computed numbers; the in-app tour follows the same arc.

1. **Problem (15 s).** Every monsoon, the haor wetlands of north-east Bangladesh flood, then drain for months. That matters for rice planting, fisheries and flood planning. Clouds hide the area from optical satellites much of that time; radar sees through.
2. **Data (20 s).** Two real NASA–ISRO NISAR L-band passes from the same orbit, 18 June and 16 October 2026. Click *Before / after* and drag the divider. Dark is smooth water; bright is land and vegetation.
3. **Discovery (20 s).** Click *Water change*. Open water shrank from about 1,766 km² to 1,469 km². The orange areas, about 308 km², drained. The water threshold is picked automatically for each image, not by hand.
4. **Is it right? (30 s).** Open *Validation & confidence*. Against NASA OPERA's cloud-free optical water map from one day later, NISAR scores F1 0.90 and IoU 0.81, and a second optical date gives F1 0.85. A completely different instrument agrees too: NASA/CNES SWOT measured every haor lake's water level falling by about 1.3 m.
5. **The innovation (25 s).** Click *L vs C band*. An independent Sentinel-1 C-band change map agrees with NISAR on 91% of tree-covered cells, but only 33% of herbaceous wetland. Short C-band waves react to wind ripples and emergent plants on shallow water; long L-band waves largely don't. That's why NISAR's L-band is the better tool for these wetlands.
6. **Honesty (15 s).** The references are satellites, not field data. They confirm that the wetlands drained, but not exactly where pixel by pixel. Depth is only measured at SWOT lakes. Everything is listed under *Data sources* and in the docs.
