export default {
  "step": 7.0,
  "events": [
    {
      "event": "planned",
      "title": "exp",
      "runs": [
        {
          "run": "20261020-183756-odd-grass/a-91ac",
          "params": {
            "m": "a"
          }
        },
        {
          "run": "20261020-183756-odd-grass/b-7ec3",
          "params": {
            "m": "b"
          }
        },
        {
          "run": "20261020-183756-odd-grass/c-7343",
          "params": {
            "m": "c"
          }
        },
        {
          "run": "20261020-183756-odd-grass/d-aaa8",
          "params": {
            "m": "d"
          }
        }
      ],
      "concurrency": 1,
      "mode": "adhoc",
      "experiment": "exp"
    },
    {
      "event": "started",
      "run": "20261020-183756-odd-grass/a-91ac",
      "params": {
        "m": "a"
      },
      "folder": "/lab/exp/runs/20261020-183756-odd-grass/a-91ac",
      "experiment": "exp"
    },
    {
      "event": "output",
      "experiment": "exp",
      "run": "20261020-183756-odd-grass/a-91ac",
      "stream": "stdout",
      "line": "start ['--m', 'a']"
    },
    {
      "event": "ended",
      "run": "20261020-183756-odd-grass/a-91ac",
      "params": {
        "m": "a"
      },
      "created": "2026-10-20T18:37:56Z",
      "ended": "2026-10-20T18:38:04Z",
      "exit_code": 0,
      "error": null,
      "experiment": "exp"
    },
    {
      "event": "started",
      "run": "20261020-183756-odd-grass/c-7343",
      "params": {
        "m": "c"
      },
      "folder": "/lab/exp/runs/20261020-183756-odd-grass/c-7343",
      "experiment": "exp"
    },
    {
      "event": "output",
      "experiment": "exp",
      "run": "20261020-183756-odd-grass/c-7343",
      "stream": "stdout",
      "line": "start ['--m', 'c']"
    },
    {
      "event": "stopping run",
      "run": "20261020-183756-odd-grass/c-7343",
      "experiment": "exp"
    },
    {
      "event": "ended",
      "run": "20261020-183756-odd-grass/c-7343",
      "params": {
        "m": "c"
      },
      "created": "2026-10-20T18:38:04Z",
      "ended": "2026-10-20T18:38:07Z",
      "exit_code": -15,
      "error": null,
      "experiment": "exp"
    },
    {
      "event": "started",
      "run": "20261020-183756-odd-grass/b-7ec3",
      "params": {
        "m": "b"
      },
      "folder": "/lab/exp/runs/20261020-183756-odd-grass/b-7ec3",
      "experiment": "exp"
    },
    {
      "event": "retried",
      "run": "20261020-183756-odd-grass/c-7343",
      "retry": "20261020-183756-odd-grass/c-7ea3",
      "params": {
        "m": "c"
      },
      "experiment": "exp"
    },
    {
      "event": "output",
      "experiment": "exp",
      "run": "20261020-183756-odd-grass/b-7ec3",
      "stream": "stdout",
      "line": "start ['--m', 'b']"
    },
    {
      "event": "ended",
      "run": "20261020-183756-odd-grass/b-7ec3",
      "params": {
        "m": "b"
      },
      "created": "2026-10-20T18:38:07Z",
      "ended": "2026-10-20T18:38:15Z",
      "exit_code": 3,
      "error": null,
      "experiment": "exp"
    },
    {
      "event": "started",
      "run": "20261020-183756-odd-grass/c-7ea3",
      "params": {
        "m": "c"
      },
      "folder": "/lab/exp/runs/20261020-183756-odd-grass/c-7ea3",
      "experiment": "exp"
    },
    {
      "event": "output",
      "experiment": "exp",
      "run": "20261020-183756-odd-grass/c-7ea3",
      "stream": "stdout",
      "line": "start ['--m', 'c']"
    },
    {
      "event": "stopping",
      "experiment": "exp"
    },
    {
      "event": "concurrency",
      "concurrency": 2,
      "experiment": "exp"
    },
    {
      "event": "ended",
      "run": "20261020-183756-odd-grass/c-7ea3",
      "params": {
        "m": "c"
      },
      "created": "2026-10-20T18:38:15Z",
      "ended": "2026-10-20T18:38:19Z",
      "exit_code": -15,
      "error": null,
      "experiment": "exp"
    },
    {
      "event": "idle",
      "experiment": "exp"
    },
    {
      "event": "done",
      "experiment": "exp",
      "error": null
    }
  ],
  "checkpoints": [
    {
      "after": 1,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 2,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "running",
          "statusStyle": "",
          "dim": false,
          "time": "0s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 4,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 5,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "running",
          "statusStyle": "",
          "dim": false,
          "time": "0s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 7,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "running",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 8,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 9,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "running",
          "statusStyle": "",
          "dim": false,
          "time": "0s"
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 10,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "running",
          "statusStyle": "",
          "dim": false,
          "time": "7s"
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7ea3",
          "params": "--m c",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 12,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "✗ exited 3",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7ea3",
          "params": "--m c",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        }
      ]
    },
    {
      "after": 13,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "✗ exited 3",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "○",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7ea3",
          "params": "--m c",
          "status": "running",
          "statusStyle": "",
          "dim": false,
          "time": "0s"
        }
      ]
    },
    {
      "after": 15,
      "title": "exp",
      "concurrency": 1,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "✗ exited 3",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "–",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7ea3",
          "params": "--m c",
          "status": "running",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        }
      ]
    },
    {
      "after": 16,
      "title": "exp",
      "concurrency": 2,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "✗ exited 3",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "–",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7ea3",
          "params": "--m c",
          "status": "running",
          "statusStyle": "",
          "dim": false,
          "time": "21s"
        }
      ]
    },
    {
      "after": 17,
      "title": "exp",
      "concurrency": 2,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "✗ exited 3",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "–",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7ea3",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "28s"
        }
      ]
    },
    {
      "after": 18,
      "title": "exp",
      "concurrency": 2,
      "rows": [
        {
          "run": "a-91ac",
          "params": "--m a",
          "status": "✓",
          "statusStyle": "",
          "dim": false,
          "time": "14s"
        },
        {
          "run": "b-7ec3",
          "params": "--m b",
          "status": "✗ exited 3",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "c-7343",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "21s"
        },
        {
          "run": "d-aaa8",
          "params": "--m d",
          "status": "–",
          "statusStyle": "dim",
          "dim": true,
          "time": ""
        },
        {
          "run": "c-7ea3",
          "params": "--m c",
          "status": "✗ exited -15",
          "statusStyle": "red",
          "dim": false,
          "time": "28s"
        }
      ]
    }
  ],
  "params": [
    [
      {
        "m": "a"
      },
      "--m a"
    ],
    [
      {
        "flag": true,
        "off": false
      },
      "--flag 1 --off 0"
    ],
    [
      {
        "n": 3,
        "x": -2
      },
      "--n 3 --x -2"
    ],
    [
      {
        "rate": 0.5
      },
      "--rate 0.5"
    ],
    [
      {
        "tags": [
          1,
          "two"
        ]
      },
      "--tags [1, \"two\"]"
    ],
    [
      {
        "cfg": {
          "a": 1,
          "b": [
            true,
            null
          ]
        }
      },
      "--cfg {\"a\": 1, \"b\": [true, null]}"
    ],
    [
      {
        "word": "with space"
      },
      "--word with space"
    ],
    [
      {
        "names": [
          "café",
          "naïve"
        ]
      },
      "--names [\"caf\\u00e9\", \"na\\u00efve\"]"
    ],
    [
      {},
      ""
    ]
  ],
  "elapsed": [
    [
      0,
      "0s"
    ],
    [
      1.9,
      "1s"
    ],
    [
      59,
      "59s"
    ],
    [
      60,
      "1m 00s"
    ],
    [
      61,
      "1m 01s"
    ],
    [
      3599,
      "59m 59s"
    ],
    [
      3600,
      "1h 00m"
    ],
    [
      3661,
      "1h 01m"
    ],
    [
      90000,
      "25h 00m"
    ]
  ]
}
