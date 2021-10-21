# Aura

Auralisation prototype for Graylog inspired by [Peep](https://www.usenix.org/legacy/publications/library/proceedings/lisa2000/full_papers/gilfix/gilfix_html/index.html). (Windows only.)

**Contents**:

- [Aura](#aura)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Use case and design](#use-case-and-design)
  - [License](#license)

## Installation

1. `git clone https://github.com/ais/aura.git`
2. `cd aura`
3. Install the list of `requirements.txt`

## Usage

Create a `config.json` in the working directory:

```json
{
  "soundFile": "string",
  "pollInterval": 0,
  "graylog": {
    "host": "string",
    "apiToken": "string",
    "requestedBy": "string",
    "streams": ["string"],
    "mean": 0
  }
}
```

The following environment variables also exist:

- `GRAYLOG_API_TOKEN` ⇒ `apiToken`
- `GRAYLOG_REQ_BY` ⇒ `requestedBy` (`X-Requested-By`)
- `AURA_CONFIG`—path to a configuration file (for switching files, or files outside the working dir).

Finally: `python play.py`.

## Use case and design

There is not always enough screen space or focus to keep attention on the logs. Email alerts are cool but distracting and don't tell you what the 'pulse' of the system is. Sometimes you like listening to music while you work.

Some background muzak (`soundFile`) plays. The message count for the last 5 minutes as a percentage of `graylog.mean` is used to slide the volume.

A frequency (1kHz/4kHz error/warn) plays for the count of errors or warnings in milliseconds.

There are two other unintended benefits:

- the volume slider in the Volume Mixer can be used as a load indicator; and
- (in remote sessions) the flakiness of the audio stream can indicate network stability.

## License

[AGPLv3](LICENSE)
