% MATLAB script to animate hand movements from a JSON file (recorded by Python GUI)
% Version 2: Added robust parsing for recordingData.frames

function animate_hand()
    % --- Configuration ---
    FIGURE_TITLE = 'MATLAB Hand Animation';
    AXIS_LIMITS = [-0.5, 1.5, -0.5, 1.5, -1, 1]; % Adjust based on your data's typical range

    % Define colors for plotting (RGB, 0-1 range)
    COLOR_WRIST = [1, 1, 0];       % Yellow
    COLOR_THUMB_TIP = [0, 1, 0];   % Green
    COLOR_FINGERTIPS = [0, 0, 1];  % Blue
    COLOR_JOINTS = [0.75, 0.75, 0.75]; % Light Gray
    COLOR_BONES = [0.86, 0.86, 0.86];  % Lighter Gray

    JOINT_SIZE = 30; 
    BONE_LINE_WIDTH = 2.5;

    % --- MediaPipe Hand Landmark Indices (1-based for MATLAB) ---
    WRIST_IDX = 1;
    THUMB_CMC_IDX = 2; THUMB_MCP_IDX = 3; THUMB_IP_IDX = 4; THUMB_TIP_IDX = 5;
    INDEX_FINGER_MCP_IDX = 6; INDEX_FINGER_PIP_IDX = 7; INDEX_FINGER_DIP_IDX = 8; INDEX_FINGER_TIP_IDX = 9;
    MIDDLE_FINGER_MCP_IDX = 10; MIDDLE_FINGER_PIP_IDX = 11; MIDDLE_FINGER_DIP_IDX = 12; MIDDLE_FINGER_TIP_IDX = 13;
    RING_FINGER_MCP_IDX = 14; RING_FINGER_PIP_IDX = 15; RING_FINGER_DIP_IDX = 16; RING_FINGER_TIP_IDX = 17;
    PINKY_MCP_IDX = 18; PINKY_PIP_IDX = 19; PINKY_DIP_IDX = 20; PINKY_TIP_IDX = 21;

    FINGERTIP_INDICES_MATLAB = [THUMB_TIP_IDX, INDEX_FINGER_TIP_IDX, MIDDLE_FINGER_TIP_IDX, RING_FINGER_TIP_IDX, PINKY_TIP_IDX];
    MAX_LANDMARK_IDX = PINKY_TIP_IDX; % Used for validation

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
    
    % --- Robustly determine numFrames and how to access frame data ---
    numFrames = 0;
    frame_data_accessor = []; % Function handle to get landmarks for a frame index

    if iscell(recordingData.frames)
        fprintf('Interpreting recordingData.frames as a cell array.\n');
        numFrames = length(recordingData.frames);
        if numFrames > 0
            % Each cell recordingData.frames{frameIdx} should contain a struct array of landmarks
            frame_data_accessor = @(idx) recordingData.frames{idx};
            % Validate first frame's content
            first_frame_content = recordingData.frames{1};
            if ~isstruct(first_frame_content)
                 fprintf('Warning: Element 1 of recordingData.frames cell array is not a struct array (Class: %s). Animation might fail.\n', class(first_frame_content));
            elseif isempty(first_frame_content)
                 fprintf('Warning: Element 1 of recordingData.frames cell array is an empty struct array. Animation might fail for this frame.\n');
            end
        end
    elseif isstruct(recordingData.frames) && ndims(recordingData.frames) == 2
        fprintf('Interpreting recordingData.frames as a 2D struct array.\n');
        numFrames = size(recordingData.frames, 1); % Assuming frames are rows
        % Each row recordingData.frames(frameIdx, :) should be a struct array of landmarks
        frame_data_accessor = @(idx) recordingData.frames(idx, :);
         if size(recordingData.frames, 2) ~= MAX_LANDMARK_IDX % Assuming 21 landmarks
             fprintf('Warning: 2D struct array does not have %d columns (has %d). Landmark indexing might be incorrect.\n', MAX_LANDMARK_IDX, size(recordingData.frames, 2));
         end
    else
        fprintf('Error: recordingData.frames is not in an expected format (cell array or 2D struct array).\n');
        fprintf('Class of recordingData.frames: %s\n', class(recordingData.frames));
        fprintf('Size of recordingData.frames: %s\n', mat2str(size(recordingData.frames)));
        return;
    end

    if numFrames == 0 || isempty(recordingData.frames) % Added isempty check for safety
        disp('No frames found in the recording data after parsing. Exiting.');
        return;
    end
    
    fps = 30; % Default FPS
    if isfield(recordingData, 'fps') && isnumeric(recordingData.fps) && recordingData.fps > 0
        fps = recordingData.fps;
    end
    actionName = 'Recorded Action';
    if isfield(recordingData, 'actionName') && (ischar(recordingData.actionName) || isstring(recordingData.actionName))
        actionName = char(recordingData.actionName); % Ensure it's char array
    end
    
    fprintf('Action: %s, Frames to animate: %d, FPS: %.2f\n', actionName, numFrames, fps);
    pauseTime = 1/fps;

    % --- Setup 3D Plot ---
    fig = figure('Name', [FIGURE_TITLE, ': ', actionName], 'NumberTitle', 'off', 'Position', [100, 100, 800, 700]);
    ax = axes('Parent', fig);
    hold(ax, 'on');
    grid(ax, 'on');
    axis(ax, AXIS_LIMITS);
    xlabel(ax, 'X coordinate');
    ylabel(ax, 'Y coordinate');
    zlabel(ax, 'Z coordinate');
    title(ax, sprintf('Frame: 1/%d - %s', numFrames, actionName));
    view(ax, 30, 20); 
    
    % --- Animation Loop ---
    hJoints = []; 
    hBones = [];  

    for frameIdx = 1:numFrames
        if ~ishandle(fig) 
            disp('Figure closed. Stopping animation.');
            break;
        end

        currentFrameLandmarks = frame_data_accessor(frameIdx); 
        
        % Validate currentFrameLandmarks (should be a 1xN_landmarks struct array)
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
            % Check if all required fields exist for the current landmark
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
        if ~isempty(hJoints), delete(hJoints); hJoints = []; end
        if ~isempty(hBones), delete(hBones); hBones = []; end

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

        % Plot Joints
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
        
        h = scatter3(ax, points(:,1), points(:,2), points(:,3), JOINT_SIZE, jointColors, 'filled');
        hJoints = [hJoints, h];

        title(ax, sprintf('Frame: %d/%d - %s', frameIdx, numFrames, actionName));
        drawnow; 
        pause(pauseTime);
    end

    if ishandle(fig)
        title(ax, sprintf('Animation Finished: %s (%d frames)', actionName, numFrames));
        disp('Animation finished.');
    end
    hold(ax, 'off');

end