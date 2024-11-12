class EventMan:
    event_dict = {}
    GLOBAL_LISTENER = 'GlobalListener'

    @classmethod
    def clear(cls):
        cls.event_dict = {}

    @classmethod
    def add(cls, event_name, callback, listener=None):
        if event_name not in cls.event_dict:
            cls.event_dict[event_name] = []

        if listener is None:
            listener = cls.GLOBAL_LISTENER

        registered = False
        for event in cls.event_dict[event_name]:
            if event['listener'] == listener:
                event['handler'].append(callback)
                registered = True
                break

        if not registered:
            cls.event_dict[event_name].append({'listener': listener, 'handler': [callback]})

    @classmethod
    def remove(cls, event_name, callback, listener=None):
        if listener is None:
            listener = cls.GLOBAL_LISTENER

        if event_name in cls.event_dict:
            for i in range(len(cls.event_dict[event_name]) - 1, -1, -1):
                event_args = cls.event_dict[event_name][i]
                if event_args['listener'] == listener:
                    if callback in event_args['handler']:
                        event_args['handler'].remove(callback)

                    if not event_args['handler']:
                        cls.event_dict[event_name].pop(i)
                    break

    @classmethod
    def trigger(cls, event_name, args=None, target=None):
        if event_name not in cls.event_dict or not cls.event_dict[event_name]:
            return

        for event in reversed(cls.event_dict[event_name]):
            if event['listener'] == target or target is None:
                for handler in event['handler']:
                    if event['listener'] == cls.GLOBAL_LISTENER:    
                        handler(args)
                    else:
                        handler(event['listener'], args)
