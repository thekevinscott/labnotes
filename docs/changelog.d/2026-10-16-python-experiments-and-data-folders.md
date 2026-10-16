**Added** — `labnotes --experiments-folder <dir> --data-folder <dir>` lists
each experiment (a subfolder with a `design.yaml`) as JSON, with the number of
runs in the data folder whose `study` matches the design's `study`. Both
folders are read with dirsql. The data folder must have a `.dirsql.toml`
declaring a `runs` table with a `study` column.
