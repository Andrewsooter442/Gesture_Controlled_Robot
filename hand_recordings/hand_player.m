% MATLAB script to animate hand movements from a JSON file (recorded by Python GUI)
% Version 4: Stabilized axes, adjusted limits for better zoom, refined setup order.

function animate_hand_from_json()
    % --- Configuration ---
    FIGURE_TITLE = 'MATLAB Hand Animation';
    % Tighter axis limits for a more "zoomed-in" view.
    % X, Y data are ~[0,1]. Z data after inversion might be ~[-0.3, 0.3].
    AXIS_LIMITS = [-0.05, 1.05, -0.05, 1.05, -0.4, 0.4]; % X, Y, Z limits

    % Define colors for plotting (RGB, 0-1 range)
    COLOR_WRIST = [1, 1, 0];       % Yellow
    COLOR_THUMB_TIP = [0, 1, 0];   % Green
    COLOR_FINGERTIPS = [0, 0, 1];  % Blue
    COLOR_JOINTS = [0.75, 0.75, 0.75]; % Light Gray
    COLOR_BONES = [0.86, 0.86, 0.86];  % Lighter Gray
    PALM_COLOR = [0.65, 0.65, 0.70]; % A slightly bluish medium Gray for palm patch
    PALM_EDGE_COLOR = [0.4, 0.4, 0.45]; % Darker edge for palm patch

    JOINT_SIZE = 35; 
    BONE_LINE_WIDTH = 3;

    % --- MediaPipe Hand Landmark Indices (1-based for MATLAB) ---
    WRIST_IDX = 1;
    THUMB_CMC_IDX = 2; THUMB_MCP_IDX = 3; THUMB_IP_IDX = 4; THUMB_TIP_IDX = 5;
    INDEX_FINGER_MCP_IDX = 6; INDEX_FINGER_PIP_IDX = 7; INDEX_FINGER_DIP_IDX = 8; INDEX_FINGER_TIP_IDX = 9;
    MIDDLE_FINGER_MCP_IDX = 10; MIDDLE_FINGER_PIP_IDX = 11; MIDDLE_FINGER_DIP_IDX = 12; MIDDLE_FINGER_TIP_IDX = 13;
    RING_FINGER_MCP_IDX = 14; RING_FINGER_PIP_IDX = 15; RING_FINGER_DIP_IDX = 16; RING_FINGER_TIP_IDX = 17;
    PINKY_MCP_IDX = 18; PINKY_PIP_IDX = 19; PINKY_DIP_IDX = 20; PINKY_TIP_IDX = 21;

    FINGERTIP_INDICES_MATLAB = [THUMB_TIP_IDX, INDEX_FINGER_TIP_IDX, MIDDLE_FINGER_TIP_IDX, RING_FINGER_TIP_IDX, PINKY_TIP_IDX];
    MAX_LANDMARK_IDX = PINKY_TIP_IDX; 

    % --- Hand Connections (pairs of 1-based landmark indices) ---
    HAND_CONNECTIONS = [
        WRIST_IDX, THUMB_CMC_IDX; WRIST_IDX, INDEX_FINGER_MCP_IDX; WRIST_IDX, PINKY_MCP_IDX;
        THUMB_CMC_IDX, THUMB_MCP_IDX; THUMB_MCP_IDX, THUMB_IP_IDX; THUMB_IP_IDX, THUMB_TIP_IDX; 
        INDEX_FINGER_MCP_IDX, INDEX_FINGER_PIP_IDX; INDEX_FINGER_PIP_IDX, INDEX_FINGER_DIP_IDX; INDEX_FINGER_DIP_IDX, INDEX_FINGER_TIP_IDX;
        MIDDLE_FINGER_MCP_IDX, MIDDLE_FINGER_PIP_IDX; MIDDLE_FINGER_PIP_IDX, MIDDLE_FINGER_DIP_IDX; MIDDLE_FINGER_DIP_IDX, MIDDLE_FINGER_TIP_IDX;
        RING_FINGER_MCP_IDX, RING_FINGER_PIP_IDX; RING_FINGER_PIP_IDX, RING_FINGER_DIP_IDX; RING_FINGER_DIP_IDX, RING_FINGER_TIP_IDX;
        PINKY_MCP_IDX, PINKY_PIP_IDX; PINKY_PIP_IDX, PINKY_DIP_IDX; PINKY_DIP_IDX, PINKY_TIP_IDX;
        INDEX_FINGER_MCP_IDX, MIDDLE_FINGER_MCP_IDX;
        MIDDLE_FINGER_MCP_IDX, RING_FINGER_MCP_IDX;
        RING_FINGER_MCP_IDX, PINKY_MCP_IDX
    ];

    % --- Palm Patch Definition (Indices for vertices of the palm polygon) ---
    PALM_VERTEX_INDICES = [WRIST_IDX, THUMB_CMC_IDX, INDEX_FINGER_MCP_IDX, MIDDLE_FINGER_MCP_IDX, RING_FINGER_MCP_IDX, PINKY_MCP_IDX];

    % --- File Selection ---
    disp('Please select the JSON recording file.');
    [fileName, pathName] = uigetfile('*.json', 'Select JSON Recording File');
    if isequal(fileName, 0) || isequal(pathName, 0)
        disp('User cancelled file selection. Exiting.');
        return;
    end
    fullFilePath = fullfile(pathName, fileName);
    fprintf('Loading recording: %s\n', fullFilePath);

    % --- Load and Parse JSON Data ---
    try
        jsonData = fileread(fullFilePath);
        recordingData = jsondecode(jsonData);
    catch ME
        fprintf('Error reading or parsing JSON file: %s\n', ME.message);
        return;
    end

    if ~isfield(recordingData, 'frames')
        disp('The "frames" field is missing in the JSON data. Exiting.');
        return;
    end
    
    numFrames = 0;
    frame_data_accessor = []; 

    if iscell(recordingData.frames)
        fprintf('Interpreting recordingData.frames as a cell array.\n');
        numFrames = length(recordingData.frames);
        if numFrames > 0
            frame_data_accessor = @(idx) recordingData.frames{idx};
        end
    elseif isstruct(recordingData.frames) && ndims(recordingData.frames) == 2
        fprintf('Interpreting recordingData.frames as a 2D struct array.\n');
        numFrames = size(recordingData.frames, 1); 
        frame_data_accessor = @(idx) recordingData.frames(idx, :);
    else
        fprintf('Error: recordingData.frames is not in an expected format.\n');
        return;
    end

    if numFrames == 0 || isempty(recordingData.frames) 
        disp('No frames found in the recording data after parsing. Exiting.');
        return;
    end
    
    fps = 30; 
    if isfield(recordingData, 'fps') && isnumeric(recordingData.fps) && recordingData.fps > 0
        fps = recordingData.fps;
    end
    actionName = 'Recorded Action';
    if isfield(recordingData, 'actionName') && (ischar(recordingData.actionName) || isstring(recordingData.actionName))
        actionName = char(recordingData.actionName); 
    end
    
    fprintf('Action: %s, Frames to animate: %d, FPS: %.2f\n', actionName, numFrames, fps);
    pauseTime = 1/fps;

    % --- Setup 3D Plot ---
    fig = figure('Name', [FIGURE_TITLE, ': ', actionName], 'NumberTitle', 'off', 'Position', [100, 100, 900, 750]);
    ax = axes('Parent', fig);
    hold(ax, 'on');
    grid(ax, 'on');
    
    % Set Data Aspect Ratio to be equal (1:1:1)
    daspect(ax, [1 1 1]); 
    
    % Set Axis Limits AFTER setting daspect
    axis(ax, AXIS_LIMITS); 
    
    xlabel(ax, 'X coordinate');
    ylabel(ax, 'Y coordinate (Screen Horizontal, Inverted Data)');
    zlabel(ax, 'Z coordinate (Screen Vertical, Inverted Depth)');
    title(ax, sprintf('Frame: 1/%d - %s', numFrames, actionName));
    
    % Set initial view to look at YZ plane (along X-axis)
     
    view(ax, 0, 90);  % azimuth=0, elevation=90

    
    % Add lighting
    camlight(ax, 'headlight'); 
    lighting gouraud; 
    material(ax, 'dull');

    % --- Animation Loop ---
    hJoints = []; 
    hBones = [];  
    hPalm = []; 

    for frameIdx = 1:numFrames
        if ~ishandle(fig) 
            disp('Figure closed. Stopping animation.');
            break;
        end

        currentFrameLandmarks = frame_data_accessor(frameIdx); 
        
        if ~isstruct(currentFrameLandmarks) || isempty(currentFrameLandmarks)
            fprintf('Warning: Frame %d data is not a struct array or is empty. Skipping frame.\n', frameIdx);
            pause(pauseTime);
            continue;
        end
        
        numLandmarksInFrame = length(currentFrameLandmarks);
        if numLandmarksInFrame < MAX_LANDMARK_IDX 
            fprintf('Warning: Frame %d has only %d landmarks, expected at least %d. Skipping frame.\n', ...
                frameIdx, numLandmarksInFrame, MAX_LANDMARK_IDX);
            pause(pauseTime);
            continue;
        end

        points = zeros(numLandmarksInFrame, 3);
        requiredFields = {'x', 'y', 'z'};
        validFrame = true;
        for lmIdx = 1:numLandmarksInFrame
            for f_idx = 1:length(requiredFields)
                if ~isfield(currentFrameLandmarks(lmIdx), requiredFields{f_idx})
                    fprintf('Warning: Landmark %d in Frame %d is missing field "%s". Skipping frame.\n', lmIdx, frameIdx, requiredFields{f_idx});
                    validFrame = false;
                    break;
                end
            end
            if ~validFrame, break; end

            points(lmIdx, 1) = currentFrameLandmarks(lmIdx).x;
            points(lmIdx, 2) = 1 - currentFrameLandmarks(lmIdx).y; % Invert Y
            points(lmIdx, 3) = -currentFrameLandmarks(lmIdx).z;   % Invert Z
        end
        
        if ~validFrame
            pause(pauseTime);
            continue;
        end

        % Clear previous frame's plots
        if ~isempty(hBones), delete(hBones); hBones = []; end
        if ~isempty(hPalm), delete(hPalm); hPalm = []; end 
        if ~isempty(hJoints), delete(hJoints); hJoints = []; end

        % Plot Bones
        for i = 1:size(HAND_CONNECTIONS, 1)
            p1_idx = HAND_CONNECTIONS(i, 1);
            p2_idx = HAND_CONNECTIONS(i, 2);
            
            if p1_idx <= numLandmarksInFrame && p2_idx <= numLandmarksInFrame
                lineX = [points(p1_idx, 1), points(p2_idx, 1)];
                lineY = [points(p1_idx, 2), points(p2_idx, 2)];
                lineZ = [points(p1_idx, 3), points(p2_idx, 3)];
                h = plot3(ax, lineX, lineY, lineZ, 'Color', COLOR_BONES, 'LineWidth', BONE_LINE_WIDTH);
                hBones = [hBones, h]; %#ok<AGROW>
            end
        end

        % Plot Palm Patch
        if all(PALM_VERTEX_INDICES <= numLandmarksInFrame) 
            palm_patch_points_x = points(PALM_VERTEX_INDICES, 1);
            palm_patch_points_y = points(PALM_VERTEX_INDICES, 2);
            palm_patch_points_z = points(PALM_VERTEX_INDICES, 3);
            
            hp = patch(ax, palm_patch_points_x, palm_patch_points_y, palm_patch_points_z, PALM_COLOR, ...
                       'EdgeColor', PALM_EDGE_COLOR, 'FaceAlpha', 0.75, 'LineWidth', 1);
            hPalm = [hPalm, hp]; %#ok<AGROW>
        end

        % Plot Joints (plotted last to be on top)
        jointColors = repmat(COLOR_JOINTS, numLandmarksInFrame, 1); 
        for lmIdx = 1:numLandmarksInFrame
            if lmIdx == WRIST_IDX
                jointColors(lmIdx, :) = COLOR_WRIST;
            elseif lmIdx == THUMB_TIP_IDX 
                jointColors(lmIdx, :) = COLOR_THUMB_TIP;
            elseif ismember(lmIdx, FINGERTIP_INDICES_MATLAB)
                jointColors(lmIdx, :) = COLOR_FINGERTIPS;
            end
        end
        
        hj = scatter3(ax, points(:,1), points(:,2), points(:,3), JOINT_SIZE, jointColors, 'filled', ...
                     'MarkerEdgeColor', [0.2 0.2 0.2]); 
        hJoints = [hJoints, hj];

        title(ax, sprintf('Frame: %d/%d - %s', frameIdx, numFrames, actionName));
        drawnow limitrate; 
        pause(pauseTime);
    end

    if ishandle(fig)
        title(ax, sprintf('Animation Finished: %s (%d frames)', actionName, numFrames));
        disp('Animation finished.');
    end
    hold(ax, 'off');

