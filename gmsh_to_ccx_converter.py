#!/usr/bin/env python3
"""
GMSH to CalculiX Converter
Converts GMSH-generated .inp files to CalculiX-compatible format

Main conversions:
1. S3 shell elements (GMSH surfaces) -> CCX *SURFACE definitions
2. Proper volume element sets (ELSET) preservation
3. Material section generation
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class GmshToCcxConverter:
    """Converts GMSH mesh to CalculiX format"""
    
    def __init__(self, gmsh_inp_path: str):
        self.gmsh_inp_path = Path(gmsh_inp_path)
        self.nodes: Dict[int, Tuple[float, float, float]] = {}
        self.shell_elements: Dict[int, List[int]] = {}  # S3 elements (surfaces)
        self.volume_elements: Dict[int, List[int]] = {}  # C3D4 elements (volumes)
        self.shell_elsets: Dict[str, List[int]] = {}  # Surface element sets
        self.volume_elsets: Dict[str, List[int]] = {}  # Volume element sets
        self.node_sets: Dict[str, List[int]] = {}  # Node sets
        
    def parse_gmsh_inp(self):
        """Parse the GMSH-generated .inp file"""
        print(f"📖 Reading GMSH file: {self.gmsh_inp_path}")
        
        with open(self.gmsh_inp_path, 'r') as f:
            lines = f.readlines()
        
        current_section = None
        current_elset = None
        current_nset = None
        current_type = None
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('**'):
                i += 1
                continue
            
            # Node section
            if line.startswith('*NODE'):
                current_section = 'NODE'
                i += 1
                continue
            
            # Element section
            if line.startswith('*ELEMENT'):
                type_match = re.search(r'TYPE=(\w+)', line, re.IGNORECASE)
                elset_match = re.search(r'ELSET=(\w+)', line, re.IGNORECASE)
                
                current_type = type_match.group(1) if type_match else None
                current_elset = elset_match.group(1) if elset_match else None
                current_section = 'ELEMENT'
                
                # Initialize the elset only if it doesn't exist yet
                if current_elset:
                    if current_type in ['S3', 'CPS3']:
                        if current_elset not in self.shell_elsets:
                            self.shell_elsets[current_elset] = []
                    elif current_type == 'C3D4':
                        if current_elset not in self.volume_elsets:
                            self.volume_elsets[current_elset] = []
                
                i += 1
                continue
            
            # Node set
            if line.startswith('*NSET'):
                nset_match = re.search(r'NSET=(\w+)', line, re.IGNORECASE)
                current_nset = nset_match.group(1) if nset_match else None
                current_section = 'NSET'
                
                if current_nset and current_nset not in self.node_sets:
                    self.node_sets[current_nset] = []
                
                i += 1
                continue
            
            # Element set (separate ELSET definitions)
            if line.startswith('*ELSET'):
                elset_match = re.search(r'ELSET=(\w+)', line, re.IGNORECASE)
                current_elset = elset_match.group(1) if elset_match else None
                current_section = 'ELSET'
                i += 1
                continue
            
            # New keyword starts - end current section
            if line.startswith('*'):
                current_section = None
                i += 1
                continue
            
            # Parse data based on current section
            if current_section == 'NODE':
                self._parse_node_line(line)
            
            elif current_section == 'ELEMENT':
                elem_id, node_list = self._parse_element_line(line)
                if elem_id is not None:
                    if current_type in ['S3', 'CPS3']:
                        self.shell_elements[elem_id] = node_list
                        if current_elset:
                            self.shell_elsets[current_elset].append(elem_id)
                    elif current_type == 'C3D4':
                        self.volume_elements[elem_id] = node_list
                        if current_elset:
                            self.volume_elsets[current_elset].append(elem_id)
            
            elif current_section == 'NSET' and current_nset:
                node_ids = [int(x.strip()) for x in line.split(',') if x.strip()]
                self.node_sets[current_nset].extend(node_ids)
            
            elif current_section == 'ELSET' and current_elset:
                elem_ids = [int(x.strip()) for x in line.split(',') if x.strip()]
                # Determine if these are shell or volume elements by checking first ID
                if elem_ids:
                    first_id = elem_ids[0]
                    if first_id in self.shell_elements:
                        if current_elset not in self.shell_elsets:
                            self.shell_elsets[current_elset] = []
                        self.shell_elsets[current_elset].extend(elem_ids)
                    elif first_id in self.volume_elements:
                        if current_elset not in self.volume_elsets:
                            self.volume_elsets[current_elset] = []
                        self.volume_elsets[current_elset].extend(elem_ids)
            
            i += 1
        
        print(f"✅ Parsed: {len(self.nodes)} nodes, "
              f"{len(self.volume_elements)} volume elements, "
              f"{len(self.shell_elements)} shell elements")
        print(f"   Volume ELSETs: {list(self.volume_elsets.keys())}")
        print(f"   Shell ELSETs: {list(self.shell_elsets.keys())}")
    
    def _parse_node_line(self, line: str):
        """Parse a node definition line"""
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) >= 4:
            node_id = int(parts[0])
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            self.nodes[node_id] = (x, y, z)
    
    def _parse_element_line(self, line: str) -> Tuple[int, List[int]]:
        """Parse an element definition line"""
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) >= 2:
            elem_id = int(parts[0])
            node_list = [int(n) for n in parts[1:]]
            return elem_id, node_list
        return None, []
    
    def find_face_match(self, shell_nodes: List[int], vol_nodes: List[int]) -> str:
        """
        Find which face of a C3D4 tetrahedron matches the shell nodes
        
        C3D4 face definitions (CalculiX convention):
        - S1: nodes 1-2-3 (base)
        - S2: nodes 1-4-2
        - S3: nodes 2-4-3
        - S4: nodes 3-4-1
        """
        # C3D4 has 4 nodes, faces have 3 nodes each
        if len(vol_nodes) != 4 or len(shell_nodes) != 3:
            return None
        
        # Define the 4 triangular faces of a tetrahedron
        faces = [
            [vol_nodes[0], vol_nodes[1], vol_nodes[2]],  # S1: nodes 1-2-3
            [vol_nodes[0], vol_nodes[3], vol_nodes[1]],  # S2: nodes 1-4-2
            [vol_nodes[1], vol_nodes[3], vol_nodes[2]],  # S3: nodes 2-4-3
            [vol_nodes[2], vol_nodes[3], vol_nodes[0]]   # S4: nodes 3-4-1
        ]
        
        shell_set = set(shell_nodes)
        
        for i, face in enumerate(faces):
            face_set = set(face)
            if shell_set == face_set:
                return f"S{i + 1}"
        
        return None
    
    def convert_surfaces(self) -> Dict[str, List[Tuple[int, str]]]:
        """
        Convert shell element sets to CCX surface definitions
        
        Returns:
            Dict mapping surface names to list of (element_id, face_id) tuples
        """
        print("\n🔄 Converting shell surfaces to CCX format...")
        
        surfaces = {}
        
        for elset_name, shell_elem_ids in self.shell_elsets.items():
            surface_defs = []
            matched = 0
            unmatched = 0
            
            for shell_id in shell_elem_ids:
                if shell_id not in self.shell_elements:
                    continue
                
                shell_nodes = self.shell_elements[shell_id]
                found = False
                
                # Search through all volume elements for a matching face
                for vol_id, vol_nodes in self.volume_elements.items():
                    face = self.find_face_match(shell_nodes, vol_nodes)
                    if face:
                        surface_defs.append((vol_id, face))
                        matched += 1
                        found = True
                        break
                
                if not found:
                    unmatched += 1
            
            if surface_defs:
                surfaces[elset_name] = surface_defs
                print(f"   {elset_name}: {matched} matched, {unmatched} unmatched")
        
        return surfaces
    
    def create_node_sets_from_surfaces(self, surfaces: Dict[str, List[Tuple[int, str]]]) -> Dict[str, Set[int]]:
        """Create node sets from surface definitions for use in BCs and loads"""
        node_sets = {}
        
        for surf_name, surf_defs in surfaces.items():
            nodes = set()
            for elem_id, face in surf_defs:
                if elem_id in self.volume_elements:
                    vol_nodes = self.volume_elements[elem_id]
                    # Extract nodes for this face
                    if face == "S1":
                        face_nodes = [vol_nodes[0], vol_nodes[1], vol_nodes[2]]
                    elif face == "S2":
                        face_nodes = [vol_nodes[0], vol_nodes[3], vol_nodes[1]]
                    elif face == "S3":
                        face_nodes = [vol_nodes[1], vol_nodes[3], vol_nodes[2]]
                    elif face == "S4":
                        face_nodes = [vol_nodes[2], vol_nodes[3], vol_nodes[0]]
                    else:
                        continue
                    nodes.update(face_nodes)
            
            if nodes:
                node_sets[surf_name] = nodes
        
        return node_sets
    
    def write_ccx_inp(self, output_path: str, surfaces: Dict[str, List[Tuple[int, str]]]):
        """Write the CalculiX-compatible .inp file"""
        print(f"\n📝 Writing CCX file: {output_path}")
        
        # Create node sets from surfaces for BCs and loads
        surface_node_sets = self.create_node_sets_from_surfaces(surfaces)
        
        # Track which elements have been written to avoid duplicates
        written_elements = set()
        
        with open(output_path, 'w') as f:
            # Header
            f.write("** =========================================\n")
            f.write("** CalculiX Input File\n")
            f.write("** Generated by GMSH to CCX Converter\n")
            f.write("** =========================================\n\n")
            
            # Nodes
            f.write("** -----------------------------------------\n")
            f.write("** NODES\n")
            f.write("** -----------------------------------------\n")
            f.write("*NODE\n")
            for node_id in sorted(self.nodes.keys()):
                x, y, z = self.nodes[node_id]
                f.write(f"{node_id}, {x}, {y}, {z}\n")
            f.write("\n")
            
            # Volume Elements (C3D4) - Write each element ONLY ONCE
            # We'll write elements grouped by their FIRST elset membership
            f.write("** -----------------------------------------\n")
            f.write("** VOLUME ELEMENTS (C3D4)\n")
            f.write("** -----------------------------------------\n")
            
            # Find which elements belong to which primary elset
            # (Volume1, Volume2, Volume3 from GMSH)
            primary_elsets = {}
            for elset_name in ['Volume1', 'Volume2', 'Volume3']:
                if elset_name in self.volume_elsets:
                    primary_elsets[elset_name] = self.volume_elsets[elset_name]
            
            # Write elements by their primary elset
            for elset_name, elem_ids in primary_elsets.items():
                f.write(f"*ELEMENT, TYPE=C3D4, ELSET={elset_name}\n")
                for elem_id in elem_ids:
                    if elem_id in self.volume_elements and elem_id not in written_elements:
                        nodes = self.volume_elements[elem_id]
                        node_str = ', '.join(map(str, nodes))
                        f.write(f"{elem_id}, {node_str}\n")
                        written_elements.add(elem_id)
                f.write("\n")
            
            # Write any remaining volume elements that weren't in primary elsets
            remaining_elements = set(self.volume_elements.keys()) - written_elements
            if remaining_elements:
                f.write("*ELEMENT, TYPE=C3D4, ELSET=OTHER_VOLUMES\n")
                for elem_id in sorted(remaining_elements):
                    nodes = self.volume_elements[elem_id]
                    node_str = ', '.join(map(str, nodes))
                    f.write(f"{elem_id}, {node_str}\n")
                    written_elements.add(elem_id)
                f.write("\n")
            
            # Now write additional ELSETs (like VOL_PIPE, VOL_WELD_UP, etc.)
            # These just REFERENCE already-written elements
            f.write("** -----------------------------------------\n")
            f.write("** ELEMENT SETS (Physical Groups)\n")
            f.write("** -----------------------------------------\n")
            
            for elset_name, elem_ids in self.volume_elsets.items():
                # Skip the primary elsets we already wrote
                if elset_name in ['Volume1', 'Volume2', 'Volume3']:
                    continue
                
                # Only write if there are volume elements in this set
                vol_elems = [eid for eid in elem_ids if eid in self.volume_elements]
                if vol_elems:
                    f.write(f"*ELSET, ELSET={elset_name}\n")
                    # Write 10 elements per line
                    for i in range(0, len(vol_elems), 10):
                        chunk = vol_elems[i:i+10]
                        f.write(', '.join(map(str, chunk)))
                        if i + 10 < len(vol_elems):
                            f.write(',\n')
                        else:
                            f.write('\n')
                    f.write("\n")
            
            # Node Sets (original ones from GMSH)
            if self.node_sets:
                f.write("** -----------------------------------------\n")
                f.write("** NODE SETS (From GMSH)\n")
                f.write("** -----------------------------------------\n")
                for nset_name, node_ids in self.node_sets.items():
                    f.write(f"*NSET, NSET={nset_name}\n")
                    # Write 10 nodes per line
                    for i in range(0, len(node_ids), 10):
                        chunk = node_ids[i:i+10]
                        f.write(', '.join(map(str, chunk)))
                        if i + 10 < len(node_ids):
                            f.write(',\n')
                        else:
                            f.write('\n')
                    f.write("\n")
            
            # Node Sets from Surfaces (for BCs and loads)
            # Only create if they don't already exist
            if surface_node_sets:
                f.write("** -----------------------------------------\n")
                f.write("** NODE SETS (From Surfaces - for BCs/Loads)\n")
                f.write("** -----------------------------------------\n")
                for surf_name, node_ids in surface_node_sets.items():
                    # Skip if this node set already exists from GMSH
                    if surf_name in self.node_sets:
                        continue
                    
                    f.write(f"*NSET, NSET={surf_name}\n")
                    sorted_nodes = sorted(node_ids)
                    # Write 10 nodes per line
                    for i in range(0, len(sorted_nodes), 10):
                        chunk = sorted_nodes[i:i+10]
                        f.write(', '.join(map(str, chunk)))
                        if i + 10 < len(sorted_nodes):
                            f.write(',\n')
                        else:
                            f.write('\n')
                    f.write("\n")
            
            # Surface Definitions (CCX format - for contact/ties)
            if surfaces:
                f.write("** -----------------------------------------\n")
                f.write("** SURFACE DEFINITIONS (For Contact/Ties)\n")
                f.write("** -----------------------------------------\n")
                for surf_name, surf_defs in surfaces.items():
                    f.write(f"*SURFACE, NAME={surf_name}, TYPE=ELEMENT\n")
                    for elem_id, face in surf_defs:
                        f.write(f"{elem_id}, {face}\n")
                    f.write("\n")
            
            f.write("** =========================================\n")
            f.write("** END OF MESH DEFINITION\n")
            f.write("** Add material properties and analysis steps below\n")
            f.write("** =========================================\n")
        
        print(f"✅ CCX file written successfully!")
        print(f"   Total elements written: {len(written_elements)}")
    
    def run(self, output_path: str):
        """Main conversion workflow"""
        print("\n" + "="*60)
        print("  GMSH to CalculiX Converter")
        print("="*60)
        
        # Step 1: Parse GMSH file
        self.parse_gmsh_inp()
        
        # Step 2: Convert surfaces
        surfaces = self.convert_surfaces()
        
        # Step 3: Write CCX file
        self.write_ccx_inp(output_path, surfaces)
        
        print("\n" + "="*60)
        print("  Conversion Complete!")
        print("="*60 + "\n")


def main():
    """Command-line interface"""
    if len(sys.argv) < 2:
        print("Usage: python gmsh_to_ccx_converter.py <input.inp> [output.inp]")
        print("\nExample:")
        print("  python gmsh_to_ccx_converter.py mesh.inp mesh_ccx.inp")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "mesh_ccx.inp"
    
    # Run conversion
    converter = GmshToCcxConverter(input_file)
    converter.run(output_file)
    
    print(f"Next steps:")
    print(f"1. Add material properties to {output_file}")
    print(f"2. Add boundary conditions and loads")
    print(f"3. Run: ccx {output_file.replace('.inp', '')}")


if __name__ == "__main__":
    main()
