# Roadmap

This document outlines the near future goals of the project. 

## 0.1.0

* Minimal viable product. 
  - [x] `codehood init` a course.
  - [x] `codehood api` for interactive exploration of the REST API/debugging.
  - [x] `codehood login` to fetch the API token from the server.
  - [x] `codehood logout` to remove the locally stored API token.
  - [x] `codehood push`:
    - [x] Push basic course information from README.md and codehood.toml.
    - [-] Push new resources. `MD`, `CODE` and `FILE` land; `LINK` waits on
      the resource manifest (`BACKLOG.md`).
    - [x] Push new questions and exams.
    - [x] Push calendar.
  - [ ] `codehood roster`:
    - [ ] Download and sync the roster file.


## 0.2.0

- [x] `codehood push`:
    - [x] Update existing resources.
    - [x] Update existing questions and exams.
    - [x] Update existing calendar.


## 0.3.0

- [ ] `codehood pull`:
  - [ ] Pull grades from the server.
- [ ] `codehood push`:
  - [x] Push grade columns computed locally (`grades.py`, `grades.csv`).
