import graphviz


def create_modelling_process_flowchart(): 
    """
    Create a flowchart for the modeling process using Graphviz.
    
    Returns:
        dot (graphviz.Digraph): The flowchart object.
    """
    
    # Create a flowchart
    dot = graphviz.Digraph(comment='The Modeling Process')
    dot.attr(rankdir='TB', size='8,5')

    # Add nodes (boxes)
    with dot.subgraph() as s:
        s.attr(rank='same')
        dot.node('A', '1. Problem Definition', shape='box')
        dot.node('B', '2. Perceptual Model', shape='box')
        dot.node('C', '3. Conceptual Model', shape='box')
        dot.node('D', '4. Model Implementation', shape='box')
        dot.node('E', '5. Model Calibration', shape='box')
        dot.node('F', '6. Model Validation', shape='box')
        dot.node('G', '7. Model Sensitivity', shape='box')
        dot.node('H', '8. Model Application', shape='box')
        dot.node('I', '9. Model Documentation & Maintenance', shape='box')
        dot.node('J', '10. Result Communication', shape='box')

    # Add edges
    # Main flow
    dot.edge('A:s', 'B:n', weight='10')
    dot.edge('B:s', 'C:n', weight='10')
    dot.edge('C:s', 'D:n', weight='10')
    dot.edge('D:s', 'E:n', weight='10')
    dot.edge('E:s', 'F:n', weight='10')
    dot.edge('F:s', 'G:n', weight='10')
    dot.edge('G:s', 'H:n', weight='10')
    dot.edge('H:s', 'I:n', weight='10')
    dot.edge('I:s', 'J:n', weight='10')

    return dot

