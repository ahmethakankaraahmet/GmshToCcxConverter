# Gmsh to CalculiX (.inp) Converter

A robust Python utility designed to bridge the gap between **Gmsh** mesh generation and **CalculiX (CCX)** simulation.

---

## The Problem
While Gmsh can export mesh files in the `.inp` (Abaqus) format, the output is often not natively compatible with CalculiX. Common issues include:
* **Header Mismatches:** Incompatible keyword formatting.
* **Element Set Definitions:** Gmsh Physical Groups not aligning with CCX `*NSET` or `*ELSET` syntax.
* **Redundant Data:** Extraneous Abaqus-specific parameters that cause CCX to error out.

## The Solution
This script automates the "cleanup" process using a generic transformation method. It ensures that the mesh, node sets, and element sets are perfectly formatted for the CalculiX input deck.

---

## Usage Method

The script is cross-platform and requires only a standard Python environment.

### Command Line
Navigate to your project folder and run:

```bash
python gmsh_to_ccx_converter.py <input.inp> [output.inp]
