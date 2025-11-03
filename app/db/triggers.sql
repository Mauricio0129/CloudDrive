-- Trigger function to update folder last_interaction when files are inserted
CREATE OR REPLACE FUNCTION update_folder_last_interaction()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.parent_folder_id IS NOT NULL THEN
        UPDATE folders
        SET last_interaction = NOW()
        WHERE id = NEW.parent_folder_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger
CREATE TRIGGER trigger_update_folder_last_interaction
    AFTER INSERT ON files
    FOR EACH ROW
    EXECUTE FUNCTION update_folder_last_interaction();