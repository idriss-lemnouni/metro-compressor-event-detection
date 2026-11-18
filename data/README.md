# Data

UCI MetroPT-3, Davari, Veloso, Ribeiro and Gama, DOI 10.24432/C5VW3R. The source represents an operating train's compressor air-production unit. The tested ZIP is 218,381,995 bytes. SHA-256 `aab991a970e58210de853bb8078ce0e63abb4d9412fdc5c79792dae3d8e1721a`. It is read directly. [UCI dataset, features, incidents and CC BY 4.0 terms](https://archive.ics.uci.edu/dataset/791/metropt%2B3%2B)

Use the provider clock for sensor readings and report dates. The source does not specify its timezone in the CSV. The pipeline checks strict timestamp order, records the actual cadence and gaps, rejects invalid sensors and collects only observed 5-minute windows with at least 20 valid rows. Features use TP2, TP3, H1, reservoir pressure (bar), oil temperature (°C) and motor current (A). The four evaluation intervals use the source's start/end columns. The second entry repeats an incident number and its maintenance comment conflicts with the event date. Use a sequential local ID and exclude that free-text date from calculations.

The source archive stays in `data/raw/` and the generated alerts stay in local `runs/`. The code license covers this implementation.
