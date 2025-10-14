        # Create sequence type
        sequence_type, = SequenceType.search([('name', '=', 'Account Journal')])
        if not sequence_type:
            sequence_type, = SequenceType.create([{
                'name': 'Account Journal',
                }])

        # Create sequence
        sequence, = SequenceStrict.create([{
            'name': 'Account Journal',
            'sequence_type': sequence_type.id,
            'company': company.id,
            }])
