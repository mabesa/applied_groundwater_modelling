import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from mpl_toolkits.mplot3d import Axes3D # Explicit import for clarity


def plot_perceptual_model(
    recharge_val="R",
    river_exchange_val="Q_riv",
    lateral_inflow_val="Q_in",
    lateral_outflow_val="Q_out",
    abstraction_val="Q_p"
):
    """
    Generates and displays a perceptual model of an urbanized river valley aquifer.

    Args:
        recharge_val (str, optional): Value or label for recharge flux. Defaults to "R".
        river_exchange_val (str, optional): Value or label for river-aquifer exchange. Defaults to "Q_riv".
        lateral_inflow_val (str, optional): Value or label for lateral groundwater inflow. Defaults to "Q_in".
        lateral_outflow_val (str, optional): Value or label for lateral groundwater outflow. Defaults to "Q_out".
        abstraction_val (str, optional): Value or label for groundwater abstraction. Defaults to "Q_p".
    """
    fig, ax = plt.subplots(figsize=(14, 10))

    # --- Define dimensions and positions (schematic) ---
    aquifer_bottom_y = 0
    aquifer_top_y = 10
    aquifer_left_x = 0
    aquifer_right_x = 20
    bedrock_depth = 2

    ground_surface_y = aquifer_top_y

    hill_material_left_x = aquifer_left_x - 4
    hill_top_y = ground_surface_y + 6

    river_channel_top_width = 3.0
    river_channel_bottom_width = 1.5
    river_depth_below_surface = 1.0
    river_water_depth = 1.5
    river_center_x = 10

    river_water_surface_y = ground_surface_y - river_depth_below_surface
    river_bed_y = river_water_surface_y - river_water_depth

    river_channel_surface_left_x = river_center_x - river_channel_top_width / 2
    river_channel_surface_right_x = river_center_x + river_channel_top_width / 2
    river_water_top_left_x = river_center_x - (river_channel_top_width / 2 - 0.5)
    river_water_top_right_x = river_center_x + (river_channel_top_width / 2 - 0.5)
    river_water_bottom_left_x = river_center_x - river_channel_bottom_width / 2
    river_water_bottom_right_x = river_center_x + river_channel_bottom_width / 2

    # Water table
    water_table_x = np.linspace(aquifer_left_x, aquifer_right_x, 100)
    base_wt_y = (
        (ground_surface_y - 3.0) # Raised slightly overall
        - 0.015 * (water_table_x - (aquifer_left_x + aquifer_right_x) / 2)**2
        + 0.04 * (water_table_x - (aquifer_left_x + aquifer_right_x) / 2)
    )
    # Increase water table on the left side
    wt_left_rise_factor = np.exp(-((water_table_x - aquifer_left_x)**2) / (2 * 3**2)) # Gaussian influence from left edge
    base_wt_y += 1.5 * wt_left_rise_factor # Boost height on the left

    water_table_y = np.clip(base_wt_y, aquifer_bottom_y + 0.5, river_bed_y - 0.2) # Ensure below river, but allow higher on left
    water_table_y = np.maximum(water_table_y, aquifer_bottom_y + 0.1)
    # Ensure WT is above lateral inflow arrow position
    lateral_in_y_target = (aquifer_bottom_y + ground_surface_y) / 2 + 0.5 # Target y for WT above arrow
    water_table_y = np.where(water_table_x < aquifer_left_x + 2, np.maximum(water_table_y, lateral_in_y_target + 0.5), water_table_y)


    # --- Draw components ---

    ax.add_patch(patches.Rectangle((hill_material_left_x, aquifer_bottom_y - bedrock_depth),
                                   (aquifer_right_x - hill_material_left_x), bedrock_depth,
                                   facecolor='dimgray', edgecolor='black', hatch='//', label='Bedrock'))
    ax.text(river_center_x, aquifer_bottom_y - bedrock_depth/2 - 0.3, 'Bedrock',
            ha='center', va='center', color='white', fontsize=10, bbox=dict(facecolor='dimgray', alpha=0.7))

    ax.add_patch(patches.Rectangle((aquifer_left_x, aquifer_bottom_y),
                                   aquifer_right_x - aquifer_left_x, ground_surface_y - aquifer_bottom_y,
                                   facecolor='sandybrown', alpha=0.7, edgecolor='black', hatch='..', label='Valley Aquifer'))
    ax.text(river_center_x, (aquifer_bottom_y + ground_surface_y)/2 - 0.5, 'Valley Aquifer', # Lowered label
            ha='center', va='center', color='black', fontsize=12)

    hill_fill_points = [
        (hill_material_left_x, hill_top_y), (aquifer_left_x, ground_surface_y),
        (aquifer_left_x, aquifer_bottom_y), (hill_material_left_x, aquifer_bottom_y)
    ]
    ax.add_patch(patches.Polygon(hill_fill_points, closed=True, facecolor='olivedrab', alpha=0.6, edgecolor='darkgreen', label='Hill Material'))
    ax.plot([hill_material_left_x, aquifer_left_x], [hill_top_y, ground_surface_y], color='darkgreen', linewidth=3.5)
    ax.text(hill_material_left_x + (aquifer_left_x - hill_material_left_x)/2, hill_top_y - 0.5, 'Hill Slope', # Adjusted y
            ha='center', va='center', fontsize=10, color='darkgreen')

    river_channel_depression_points = [
        (river_channel_surface_left_x, ground_surface_y),
        (river_water_top_left_x, river_water_surface_y),
        (river_water_bottom_left_x, river_bed_y),
        (river_water_bottom_right_x, river_bed_y),
        (river_water_top_right_x, river_water_surface_y),
        (river_channel_surface_right_x, ground_surface_y)
    ]
    ax.add_patch(patches.Polygon(river_channel_depression_points, closed=False, fill=False, edgecolor='saddlebrown', linewidth=2.5))

    river_water_points = [
        (river_water_top_left_x, river_water_surface_y), (river_water_bottom_left_x, river_bed_y),
        (river_water_bottom_right_x, river_bed_y), (river_water_top_right_x, river_water_surface_y)
    ]
    ax.add_patch(patches.Polygon(river_water_points, closed=True, facecolor='lightblue', alpha=0.8, edgecolor='blue', label='River Water'))
    ax.text(river_center_x, river_water_surface_y - river_water_depth/2 - 0.1, 'River', # Adjusted y
            ha='center', va='center', color='darkblue', fontsize=10, bbox=dict(facecolor='lightblue', alpha=0.7))

    ax.plot([aquifer_left_x, river_channel_surface_left_x], [ground_surface_y, ground_surface_y], color='darkgreen', linewidth=3.5)
    ax.plot([river_channel_surface_right_x, aquifer_right_x], [ground_surface_y, ground_surface_y], color='darkgreen', linewidth=3.5)
    ax.text(aquifer_right_x - 0.5, ground_surface_y + 0.4, 'Valley Floor', ha='right', va='bottom', fontsize=9, color='darkgreen')

    building_y_bottom = ground_surface_y
    building_height = 2.5
    building_width = 1.8
    building1_x = aquifer_left_x + 1.5
    if building1_x + building_width < river_channel_surface_left_x:
        ax.add_patch(patches.Rectangle((building1_x, building_y_bottom), building_width, building_height,
                                   facecolor='silver', edgecolor='black', label='Urban Area'))
        ax.text(building1_x + building_width/2, building_y_bottom + building_height/2 + 0.1, 'Urban', # Adjusted y
                ha='center', va='center', fontsize=8, rotation=90)
    building2_x = aquifer_right_x - 2 - building_width
    if building2_x > river_channel_surface_right_x:
        ax.add_patch(patches.Rectangle((building2_x, building_y_bottom), building_width, building_height,
                                   facecolor='silver', edgecolor='black'))
        ax.text(building2_x + building_width/2, building_y_bottom + building_height/2 + 0.1, 'Urban', # Adjusted y
                ha='center', va='center', fontsize=8, rotation=90)

    ax.plot(water_table_x, water_table_y, color='blue', linestyle='--', linewidth=2.5, label='Water Table')
    # Find a good spot for WT label, avoiding hill and river
    wt_label_x = aquifer_left_x + (river_channel_surface_left_x - aquifer_left_x) / 2 + 2.5
    wt_label_y = np.interp(wt_label_x, water_table_x, water_table_y) + 0.3
    ax.text(wt_label_x, wt_label_y, 'Water Table', ha='center', va='bottom', color='blue', fontsize=10)


    # --- Fluxes ---
    arrow_style = dict(facecolor='red', shrink=0.05, width=1.5, headwidth=6, alpha=0.8)
    flux_text_style = dict(ha='center', va='center', fontsize=8, color='darkred', bbox=dict(facecolor='white', alpha=0.6, pad=0.1)) # Smaller pad

    # 1. Recharge
    recharge_hill_x = hill_material_left_x + (aquifer_left_x - hill_material_left_x) / 2
    recharge_hill_y_surface = np.interp(recharge_hill_x, [hill_material_left_x, aquifer_left_x], [hill_top_y, ground_surface_y])
    ax.annotate('', xy=(recharge_hill_x, recharge_hill_y_surface - 1.5), xytext=(recharge_hill_x, recharge_hill_y_surface + 1.0),
                arrowprops=arrow_style)
    ax.text(recharge_hill_x, recharge_hill_y_surface + 1.5, f'Recharge\n({recharge_val})', **flux_text_style)

    recharge_valley_x = river_channel_surface_right_x + 2.5 # Moved further right
    if recharge_valley_x < aquifer_right_x -1:
        recharge_valley_y_start = ground_surface_y + 1.5
        recharge_valley_y_end = np.interp(recharge_valley_x, water_table_x, water_table_y)
        ax.annotate('', xy=(recharge_valley_x, recharge_valley_y_end + 0.1), xytext=(recharge_valley_x, recharge_valley_y_start),
                    arrowprops=arrow_style)
        ax.text(recharge_valley_x, recharge_valley_y_start + 0.5, f'Recharge\n({recharge_val})', **flux_text_style) # Added label

    # 2. River-Aquifer Interaction
    interaction_x = river_center_x
    interaction_y_start = river_bed_y - 0.1
    interaction_y_end = np.interp(interaction_x, water_table_x, water_table_y) + 0.2
    if river_bed_y > interaction_y_end + 0.2:
        ax.annotate('', xy=(interaction_x, interaction_y_end), xytext=(interaction_x, interaction_y_start),
                    arrowprops=arrow_style)
        ax.text(interaction_x + 2.0, (interaction_y_start + interaction_y_end)/2 + 0.2, f'River Seepage\n({river_exchange_val})', **flux_text_style) # Adjusted position

    # 3. Lateral Groundwater Flow
    lateral_in_y = (aquifer_bottom_y + ground_surface_y) / 2 - 0.5 # Lowered arrow slightly
    lateral_in_x_start = aquifer_left_x - 0.5
    lateral_in_x_end = aquifer_left_x + 1.0
    ax.annotate('', xy=(lateral_in_x_end, lateral_in_y), xytext=(lateral_in_x_start, lateral_in_y),
                arrowprops=arrow_style)
    ax.text(lateral_in_x_start - 1.2, lateral_in_y, f'Lateral\nInflow\n({lateral_inflow_val})', **flux_text_style) # Adjusted position

    lateral_out_y = (aquifer_bottom_y + np.interp(aquifer_right_x - 0.1, water_table_x, water_table_y))/2 + 0.5 # Adjusted y
    lateral_out_x_start = aquifer_right_x - 0.1
    lateral_out_x_end = aquifer_right_x + 1.5
    ax.annotate('', xy=(lateral_out_x_end, lateral_out_y), xytext=(lateral_out_x_start, lateral_out_y),
                arrowprops=arrow_style)
    ax.text(lateral_out_x_end + 0.9, lateral_out_y, f'Lateral\nOutflow\n({lateral_outflow_val})', **flux_text_style) # Adjusted position

    # 4. Groundwater Abstraction
    well_x = aquifer_right_x - 3.5 # Adjusted position
    if well_x > river_channel_surface_right_x + 1.0 :
        well_screen_bottom_y = aquifer_bottom_y + 1
        well_screen_top_y = np.interp(well_x, water_table_x, water_table_y) - 0.5
        well_screen_top_y = max(well_screen_top_y, well_screen_bottom_y + 0.5)
        ax.plot([well_x, well_x], [ground_surface_y, well_screen_bottom_y], color='gray', linewidth=3)
        ax.plot([well_x, well_x], [well_screen_top_y, well_screen_bottom_y], color='darkgray', linewidth=5, linestyle=':', solid_capstyle='butt')
        ax.text(well_x, ground_surface_y + 0.4, 'Well', ha='center', va='bottom', fontsize=9) # Adjusted y
        abstraction_y_start = (well_screen_bottom_y + well_screen_top_y) / 2
        ax.annotate('', xy=(well_x + 1.5, abstraction_y_start + 1), xytext=(well_x + 0.1, abstraction_y_start),
                    arrowprops=arrow_style)
        ax.text(well_x + 1.8, abstraction_y_start + 1.5, f'Abstraction\n({abstraction_val})', **flux_text_style) # Adjusted position

    # --- Final plot adjustments ---
    ax.set_xlim(hill_material_left_x - 1, aquifer_right_x + 3)
    ax.set_ylim(aquifer_bottom_y - bedrock_depth - 1, hill_top_y + 2)
    ax.set_xlabel("Horizontal Distance (Schematic)")
    ax.set_ylabel("Elevation (Schematic)")
    ax.set_title("Perceptual Model: Urbanized River Valley Aquifer with Hill Slope (Initial)", fontsize=15, pad=20)

    handles, labels = ax.get_legend_handles_labels()
    if not any(label == 'Fluxes (Conceptual)' for label in labels):
        handles.append(patches.Patch(facecolor='red', alpha=0.8, label='Fluxes (Conceptual)'))
        labels.append('Fluxes (Conceptual)')
    ax.legend(handles=handles, labels=labels, loc='upper left', bbox_to_anchor=(0.01, 0.98), fontsize=8, ncol=2) # Smaller font for legend

    ax.grid(True, linestyle=':', alpha=0.5)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()

def plot_perceptual_model_3d(
    recharge_val="R",
    river_exchange_val="Q_riv",
    lateral_inflow_val="Q_in",
    lateral_outflow_val="Q_out",
    abstraction_val="Q_p"
):
    """
    Generates and displays a 3D perceptual model of an urbanized river valley aquifer.
    Note: This is a conceptual 3D representation.

    Args:
        recharge_val (str, optional): Value or label for recharge flux. Defaults to "R".
        river_exchange_val (str, optional): Value or label for river-aquifer exchange. Defaults to "Q_riv".
        lateral_inflow_val (str, optional): Value or label for lateral groundwater inflow. Defaults to "Q_in".
        lateral_outflow_val (str, optional): Value or label for lateral groundwater outflow. Defaults to "Q_out".
        abstraction_val (str, optional): Value or label for groundwater abstraction. Defaults to "Q_p".
    """
    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_box_aspect([2, 1.5, 0.8])


    # --- Dimensions ---
    valley_len_x = 20
    valley_width_y = 12
    aquifer_base_z = 0
    aquifer_thickness = 4
    valley_floor_z = aquifer_base_z + aquifer_thickness
    hill_crest_z = valley_floor_z + 5

    # --- Bedrock Base ---
    X_bed, Y_bed = np.meshgrid(np.linspace(0, valley_len_x, 5), np.linspace(0, valley_width_y, 5))
    Z_bed = np.full_like(X_bed, aquifer_base_z - 0.5)
    ax.plot_surface(X_bed, Y_bed, Z_bed, color='dimgray', alpha=0.4, rstride=1, cstride=1)

    # --- Aquifer Volume ---
    aq_x_coords_arr = np.array([0, valley_len_x, valley_len_x, 0, 0])
    aq_y_min = valley_width_y * 0.2
    aq_y_max = valley_width_y * 0.8
    aq_y_coords_arr = [aq_y_min, aq_y_min, aq_y_max, aq_y_max, aq_y_min]

    X_aq_bottom, Y_aq_bottom = np.meshgrid(np.linspace(0, valley_len_x, 5), np.linspace(aq_y_min, aq_y_max, 5))
    Z_aq_bottom = np.full_like(X_aq_bottom, aquifer_base_z)
    ax.plot_surface(X_aq_bottom, Y_aq_bottom, Z_aq_bottom, color='sandybrown', alpha=0.3, rstride=1, cstride=1)

    X_aq_top, Y_aq_top = np.meshgrid(np.linspace(0, valley_len_x, 5), np.linspace(aq_y_min, aq_y_max, 5))
    Z_aq_top = np.full_like(X_aq_top, valley_floor_z)
    ax.plot_surface(X_aq_top, Y_aq_top, Z_aq_top, color='sandybrown', alpha=0.6, rstride=1, cstride=1, label='Aquifer Material')

    for i in range(4):
        ax.plot([aq_x_coords_arr[i], aq_x_coords_arr[i+1]], [aq_y_coords_arr[i], aq_y_coords_arr[i+1]], aquifer_base_z, color='saddlebrown', linestyle=':')
        ax.plot([aq_x_coords_arr[i], aq_x_coords_arr[i+1]], [aq_y_coords_arr[i], aq_y_coords_arr[i+1]], valley_floor_z, color='saddlebrown', linestyle='-')
        ax.plot([aq_x_coords_arr[i], aq_x_coords_arr[i]], [aq_y_coords_arr[i], aq_y_coords_arr[i]], [aquifer_base_z, valley_floor_z], color='saddlebrown', linestyle='-')
    ax.text(valley_len_x/2, (aq_y_min+aq_y_max)/2, valley_floor_z + 0.5, 'Valley Aquifer', color='black', ha='center', va='bottom', fontsize=9)

    # --- Valley Slope / Hill Material (Only one side shown - the one at higher Y values) ---
    X_hill_r, Y_hill_r = np.meshgrid(np.linspace(0, valley_len_x, 5), np.linspace(aq_y_max, valley_width_y, 5))
    Z_hill_r = valley_floor_z + ((Y_hill_r - aq_y_max) / (valley_width_y - aq_y_max)) * (hill_crest_z - valley_floor_z)
    ax.plot_surface(X_hill_r, Y_hill_r, Z_hill_r, color='olivedrab', alpha=0.7, rstride=1, cstride=1, label='Hill Material')
    ax.text(valley_len_x/2, valley_width_y*0.95, hill_crest_z -0.5, 'Hill Slope', color='darkgreen', ha='center', va='center', fontsize=9)

    # --- River ---
    river_y_center = valley_width_y / 2
    river_x_coords = np.linspace(0, valley_len_x, 50)
    river_y_coords = np.full_like(river_x_coords, river_y_center)
    river_z_coords = np.full_like(river_x_coords, valley_floor_z - 0.1)
    ax.plot(river_x_coords, river_y_coords, river_z_coords, color='blue', linewidth=4, label='River')
    ax.text(valley_len_x*0.9, river_y_center + 0.5, valley_floor_z + 0.2, 'River', color='darkblue', ha='center', fontsize=9)

    # --- Urban Area ---
    n_buildings = 2
    building_lwh = [1.5, 1, 2.5]
    for i in range(n_buildings):
        b_x = valley_len_x * (0.3 + 0.3*i)
        b_y = river_y_center + (building_lwh[1] if i % 2 == 0 else -building_lwh[1]*1.5)
        if aq_y_min < b_y < aq_y_max - building_lwh[1]:
             ax.bar3d(b_x, b_y, valley_floor_z, building_lwh[0], building_lwh[1], building_lwh[2], color='silver', alpha=0.9, shade=True)
    if n_buildings > 0:
        ax.text(valley_len_x * 0.35, river_y_center + building_lwh[1]*2.5, valley_floor_z + building_lwh[2] + 0.2, "Urban Area", color='black', ha='center', va='bottom', fontsize=8)

    # --- Flux Arrows ---
    arrow_len_factor = 2.0
    arrow_color = 'red'
    q_kwargs = {'length': arrow_len_factor, 'normalize': False, 'arrow_length_ratio': 0.4, 'color': arrow_color, 'linewidth': 1.5}
    text_kwargs = {'color': 'darkred', 'ha': 'center', 'va': 'center', 'fontsize': 7}

    # 1. Recharge
    # On remaining hill
    ax.quiver(valley_len_x*0.25, valley_width_y*0.9, hill_crest_z * 0.9, 0, 0, -arrow_len_factor*0.8, **q_kwargs)
    ax.text(valley_len_x*0.25, valley_width_y*0.9, hill_crest_z*0.9 + 0.7, f'Recharge\n({recharge_val})', **text_kwargs)
    # On valley floor
    ax.quiver(valley_len_x*0.75, river_y_center -1, valley_floor_z + arrow_len_factor, 0, 0, -arrow_len_factor, **q_kwargs)
    ax.text(valley_len_x*0.75, river_y_center -1, valley_floor_z + arrow_len_factor + 0.7, f'Recharge\n({recharge_val})', **text_kwargs)

    # 2. River-Aquifer Interaction
    riv_int_x = valley_len_x * 0.5
    riv_int_z_start = river_z_coords[0]
    aq_mid_z = aquifer_base_z + aquifer_thickness / 2
    ax.quiver(riv_int_x, river_y_center, riv_int_z_start, 0, 0, aq_mid_z - riv_int_z_start, length=abs(aq_mid_z - riv_int_z_start)*0.7, normalize=False, arrow_length_ratio=0.3, color=arrow_color, linewidth=1.5)
    ax.text(riv_int_x + 1.5, river_y_center, (riv_int_z_start + aq_mid_z)/2, f'River Seepage\n({river_exchange_val})', **text_kwargs)  # , ha='left')

    # 3. Lateral Inflow (from the side where hill was removed - conceptual from valley edge at lower Y)
    inflow_x = valley_len_x * 0.2
    inflow_y_start = aq_y_min - 0.5
    inflow_y_end = aq_y_min + 0.5
    inflow_z = aquifer_base_z + aquifer_thickness * 0.7
    ax.quiver(inflow_x, inflow_y_start, inflow_z, 0, (inflow_y_end - inflow_y_start), 0, **q_kwargs)
    ax.text(inflow_x, inflow_y_start - 1.2, inflow_z, f'Lateral Inflow\n({lateral_inflow_val})', **text_kwargs)  # , va='top')

    # 4. Lateral Outflow
    outflow_x_start = valley_len_x - arrow_len_factor
    outflow_y = (aq_y_min + aq_y_max) / 2
    outflow_z = aquifer_base_z + aquifer_thickness / 2
    ax.quiver(outflow_x_start, outflow_y, outflow_z, arrow_len_factor, 0, 0, **q_kwargs)
    ax.text(outflow_x_start + arrow_len_factor/2, outflow_y + 1.8, outflow_z, f'Lateral Outflow\n({lateral_outflow_val})', **text_kwargs)  # , ha='left')

    # 5. Abstraction
    abs_x = valley_len_x * 0.65
    abs_y = (aq_y_min + aq_y_max) / 2 + 1
    abs_z_start = aquifer_base_z + aquifer_thickness * 0.3
    abs_z_end = valley_floor_z + 1.0
    ax.quiver(abs_x, abs_y, abs_z_start, 0, 0, (abs_z_end - abs_z_start), length=arrow_len_factor*0.6, normalize=False, arrow_length_ratio=0.3, color=arrow_color, linewidth=1.5)
    ax.plot([abs_x, abs_x], [abs_y, abs_y], [aquifer_base_z, valley_floor_z + 0.2], color='gray', linewidth=2.5)
    ax.text(abs_x, abs_y - 1.5, abs_z_end + 0.2, f'Abstraction\n({abstraction_val})', **text_kwargs)  # , ha='center', va='bottom')

    # --- Settings, Labels, Legend ---
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_zlabel("")

    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_zticklabels([])

    ax.grid(False) # Remove grid lines

    ax.set_title("3D Perceptual Model: Valley Aquifer System", fontsize=16, pad=10)

    ax.view_init(elev=25, azim=-125)

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='sandybrown', lw=4, label='Aquifer Material'),
        Line2D([0], [0], color='olivedrab', lw=4, label='Hill Material'),
        Line2D([0], [0], color='blue', lw=2, label='River'),
        plt.Rectangle((0,0),1,1, fc="silver", label='Urban Area'),
        Line2D([0], [0], marker='o', markerfacecolor=arrow_color, markeredgecolor=arrow_color, markersize=0,
               linestyle='-', linewidth=1.5, color=arrow_color, label='Fluxes')
    ]
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0.0, 0.95), fontsize=9)

    plt.tight_layout(pad=0.1)
    plt.show()

if __name__ == '__main__':
    plot_perceptual_model()