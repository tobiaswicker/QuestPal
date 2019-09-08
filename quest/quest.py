class Quest:

    def __init__(self, stop_id, stop_name, latitude, longitude, timestamp, pokemon_id, item_id, item_amount, task):

        self.stop_id = stop_id
        self.stop_name = stop_name
        self.latitude = latitude
        self.longitude = longitude
        self.timestamp = timestamp
        self.pokemon_id = pokemon_id
        self.item_id = item_id
        self.item_amount = item_amount
        self.task = task
