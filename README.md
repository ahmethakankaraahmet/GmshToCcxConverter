# Gmsh to CalculiX (.inp) Converter

A Python utility designed to bridge the gap between **Gmsh** mesh generation and **CalculiX (CCX)** simulation.

---

## The Problem
While Gmsh can export mesh files in the `.inp` (Abaqus) format, the output is often not natively compatible with CalculiX. Differences in keyword handling, element set definitions, and header formatting can cause CCX to throw errors during the input phase.

## The Proposed Solution
This script automates the "cleanup" process, applying a generic transformation method to ensure the generated `.inp` file aligns perfectly with the CalculiX input deck requirements.

---

## Usage Method

The script is cross-platform and requires only a standard Python environment.

### Command Line
Navigate to your project folder and run:

```bash
python gmsh_to_ccx_converter.py <input.inp> [output.inp]
